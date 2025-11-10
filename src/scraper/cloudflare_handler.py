from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .logger import get_logger
from .proxy_manager import ProxyManager
from .js_executor import execute_js
from .html_collector import collect_html
from ..utils.retry_handler import retry_policy

logger = get_logger(__name__)

@dataclass
class BrowserConfig:
    headless: bool = True
    navigation_timeout_ms: int = 45000
    user_agent: Optional[str] = None
    chromium_channel: Optional[str] = "chrome"
    viewport: Optional[Dict[str, int]] = None

class CloudflareHandler:
    """
    Navigate to a URL using Playwright and attempt to get fully rendered HTML.
    Implements basic waiting heuristics that often get past Cloudflare 'Checking your browser' gates.
    """

    def __init__(self, proxy_manager: ProxyManager, cfg: BrowserConfig, js_wait_ms: int = 1500):
        self.proxy_manager = proxy_manager
        self.cfg = cfg
        self.js_wait_ms = js_wait_ms

    async def _ensure_playwright_browsers(self) -> None:
        """
        Ensure Playwright browsers are installed. If not, attempt installation.
        """
        try:
            # Quick smoke test: try launching a short-lived playwright process
            # If it fails due to missing browsers, run `playwright install`.
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", "import sys; from playwright.async_api import async_playwright; print('ok')",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
        except Exception:
            pass  # Best-effort check

        # Try a no-op 'playwright install' in case browsers are missing
        try:
            subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=False, capture_output=True)
        except Exception:
            # Non-fatal; user may have already installed runtimes
            pass

    async def _new_context(self, p, proxy_url: Optional[str]):
        launch_kwargs: Dict[str, Any] = {
            "headless": self.cfg.headless,
        }
        if self.cfg.chromium_channel:
            browser = await p.chromium.launch(channel=self.cfg.chromium_channel, **launch_kwargs)
        else:
            browser = await p.chromium.launch(**launch_kwargs)

        context_args: Dict[str, Any] = {}
        if proxy_url:
            context_args["proxy"] = {"server": proxy_url}

        if self.cfg.user_agent:
            context_args["user_agent"] = self.cfg.user_agent
        if self.cfg.viewport:
            context_args["viewport"] = self.cfg.viewport

        context = await browser.new_context(**context_args)
        context.set_default_navigation_timeout(self.cfg.navigation_timeout_ms)
        context.set_default_timeout(self.cfg.navigation_timeout_ms)
        return browser, context

    async def _wait_cloudflare(self, page) -> None:
        """
        Heuristics to wait out common Cloudflare interstitials.
        """
        await asyncio.sleep(1.0)  # give a moment for any challenge to appear
        text_candidates = [
            "Checking your browser",
            "Verifying you are human",
            "Just a moment",
            "Security check",
        ]
        try:
            # If any of these texts are present, wait a bit longer.
            content = await page.content()
            if any(t.lower() in content.lower() for t in text_candidates):
                logger.info("Cloudflare challenge detected; waiting…")
                # Cloudflare challenges typically resolve within a few seconds.
                # Wait in short intervals, up to ~20s.
                for _ in range(20):
                    await asyncio.sleep(1.0)
                    content = await page.content()
                    if not any(t.lower() in content.lower() for t in text_candidates):
                        break
        except Exception:
            # Heuristic only; proceed regardless.
            pass

    @retry_policy()  # default max_attempts=3; caller may wrap with a different policy if needed
    async def fetch(self, url: str, js_script: Optional[str]) -> Dict[str, Any]:
        """
        Navigate to URL with optional JS execution and return a dict:
          { "url": str, "result_from_js_script": Any, "html": str }
        """
        proxy = self.proxy_manager.next()
        if proxy:
            logger.info(f"Using proxy: {proxy}")

        await self._ensure_playwright_browsers()

        async with async_playwright() as p:
            browser = None
            context = None
            try:
                browser, context = await self._new_context(p, proxy)
                page = await context.new_page()

                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded")

                # Try to reach a more "settled" state
                try:
                    await page.wait_for_load_state("networkidle", timeout=self.cfg.navigation_timeout_ms)
                except PlaywrightTimeoutError:
                    logger.info("Timed out waiting for network idle; continuing with best-effort HTML.")

                await self._wait_cloudflare(page)

                # Optional extra wait to let JS-heavy pages finish rendering
                await asyncio.sleep(self.js_wait_ms / 1000.0)

                js_result = await execute_js(page, js_script)
                html = await collect_html(page)

                return {
                    "url": url,
                    "result_from_js_script": js_result,
                    "html": html,
                }
            finally:
                if context:
                    await context.close()
                if browser:
                    await browser.close()