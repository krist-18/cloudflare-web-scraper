from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from scraper.logger import get_logger
from scraper.proxy_manager import ProxyManager
from scraper.cloudflare_handler import CloudflareHandler, BrowserConfig

logger = get_logger(__name__)

def load_settings(settings_path: Path) -> Dict[str, Any]:
    with settings_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_input(input_path: Path) -> List[Dict[str, Any]]:
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of objects.")
    for item in data:
        if "url" not in item:
            raise ValueError("Each input item must include a 'url' field.")
    return data

async def run(input_items: List[Dict[str, Any]], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    proxy_mgr = ProxyManager(settings.get("proxies") or [])
    cfg = BrowserConfig(
        headless=bool(settings.get("headless", True)),
        navigation_timeout_ms=int(settings.get("navigation_timeout_ms", 45000)),
        user_agent=settings.get("user_agent"),
        chromium_channel=settings.get("chromium_channel", "chrome"),
        viewport=settings.get("viewport"),
    )
    handler = CloudflareHandler(proxy_mgr, cfg, js_wait_ms=int(settings.get("js_wait_ms", 1500)))

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(input_items, start=1):
        url: str = item["url"]
        js_script: Optional[str] = item.get("js_script")
        logger.info(f"[{idx}/{len(input_items)}] Processing {url}")
        try:
            result = await handler.fetch(url, js_script)
            results.append(result)
            logger.info(f"OK: {url}")
        except Exception as exc:
            logger.error(f"Failed: {url} - {exc}")
            results.append({"url": url, "error": str(exc)})
    return results

def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    default_input = repo_root / "data" / "input.sample.json"
    default_output = repo_root / "data" / "output.sample.json"
    default_settings = repo_root / "src" / "config" / "settings.json"

    parser = argparse.ArgumentParser(
        description="Cloudflare Web Scraper - fetch rendered HTML and optional JS results."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(default_input),
        help="Path to input JSON (list of {url, js_script?}).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(default_output),
        help="Path to write output JSON.",
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=str(default_settings),
        help="Path to settings.json.",
    )
    args = parser.parse_args()

    settings_path = Path(args.settings)
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not settings_path.exists():
        raise FileNotFoundError(f"Settings not found: {settings_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    settings = load_settings(settings_path)
    input_items = load_input(input_path)

    # Allow env var override for headless mode (useful during debugging)
    env_headless = os.getenv("HEADLESS")
    if env_headless is not None:
        settings["headless"] = env_headless.lower() in ("1", "true", "yes")

    results = asyncio.run(run(input_items, settings))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"Wrote {len(results)} records -> {output_path}")

if __name__ == "__main__":
    main()