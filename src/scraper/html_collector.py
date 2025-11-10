from __future__ import annotations

from playwright.async_api import Page

async def collect_html(page: Page) -> str:
    """
    Return the full rendered HTML of the current page.
    """
    return await page.content()