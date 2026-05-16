# ============================================================
# browser/browser_engine.py — Playwright Browser Controller
# Shared async browser instance, tab management
# ============================================================

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("freya.browser")

_playwright = None
_browser = None
_context = None
_page = None
_loop: Optional[asyncio.AbstractEventLoop] = None


async def init_browser(headless: bool = False) -> bool:
    """Initialize Playwright browser (Chromium). Returns True on success."""
    global _playwright, _browser, _context, _page
    try:
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-first-run",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ]
        )
        _context = await _browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        _page = await _context.new_page()
        logger.info("Playwright browser initialized ✓")
        return True
    except Exception as e:
        logger.error("Browser init failed: %s", e)
        return False


async def get_browser_page():
    """Get the active page, initializing browser if needed."""
    global _page, _browser, _context
    if _browser is None or not _browser.is_connected():
        await init_browser()
    if _page is None or _page.is_closed():
        _page = await _context.new_page()
    return _page


async def new_tab(url: str = "") -> object:
    """Open a new tab."""
    global _context
    if _context is None:
        await init_browser()
    page = await _context.new_page()
    if url:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return page


async def close_browser():
    """Clean up browser resources."""
    global _playwright, _browser, _context, _page
    try:
        if _browser:
            await _browser.close()
        if _playwright:
            await _playwright.stop()
        _playwright = _browser = _context = _page = None
        logger.info("Browser closed.")
    except Exception as e:
        logger.error("Browser close error: %s", e)


async def go_to(url: str) -> str:
    page = await get_browser_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return f"Navigated to {url}"


async def get_page_title() -> str:
    page = await get_browser_page()
    return await page.title()


async def get_page_text(max_chars: int = 2000) -> str:
    """Extract visible text from current page."""
    page = await get_browser_page()
    try:
        text = await page.evaluate("() => document.body.innerText")
        return text[:max_chars]
    except Exception:
        return ""


def run_async(coro):
    """Run an async coroutine from sync context safely."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    else:
        return asyncio.run(coro)
