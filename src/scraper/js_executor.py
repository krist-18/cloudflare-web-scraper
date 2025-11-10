from __future__ import annotations

from typing import Any, Optional

from playwright.async_api import Page

async def execute_js(page: Page, script: Optional[str]) -> Any:
    """
    Execute a user-supplied JS snippet in the page context.
    The snippet should be an expression or an IIFE and must be safe to run.
    Returns the value produced by the expression.
    """
    if not script:
        return None
    try:
        # We evaluate the provided script as-is. Users should provide an expression/IIFE.
        return await page.evaluate(script)
    except Exception as exc:
        # Surface errors but don't break the whole run; caller can decide.
        return {"error": str(exc)}