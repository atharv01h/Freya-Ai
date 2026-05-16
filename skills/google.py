# ============================================================
# skills/google.py — Google Search via Playwright
# ============================================================

import logging
import webbrowser
import urllib.parse

logger = logging.getLogger("freya.skills.google")


async def search_google(query: str) -> str:
    """Open Google search using Playwright."""
    try:
        from browser.browser_engine import get_browser_page
        page = await get_browser_page()
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return f"Showing Google results for '{query}'."
    except Exception as e:
        logger.error("Google search error: %s", e)
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        return f"Opened Google for '{query}'."


async def get_top_google_result(query: str) -> str:
    """Search Google and return the text snippet of the top result."""
    try:
        from browser.browser_engine import get_browser_page
        page = await get_browser_page()
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        # Try to grab featured snippet or first result description
        selectors = [
            "div.BNeawe",
            "div[data-tts='answers']",
            "div.kCrYT",
            "span.hgKElc",
        ]
        for sel in selectors:
            el = page.locator(sel).first
            if await el.count() > 0:
                text = await el.inner_text()
                if text.strip():
                    return text.strip()[:400]
        return f"Opened Google search for '{query}'."
    except Exception as e:
        logger.error("Google result fetch error: %s", e)
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        return f"Opened Google for '{query}'."


def search_google_sync(query: str) -> str:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, search_google(query)).result(timeout=20)
        return loop.run_until_complete(search_google(query))
    except Exception:
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        return f"Opened Google for '{query}'."
