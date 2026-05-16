# ============================================================
# skills/youtube.py — YouTube Automation via Playwright
# ============================================================

import logging
logger = logging.getLogger("freya.skills.youtube")


async def search_youtube(query: str) -> str:
    """Open YouTube and search for a query using Playwright."""
    try:
        from browser.browser_engine import get_browser_page
        page = await get_browser_page()
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return f"Searching YouTube for '{query}'."
    except Exception as e:
        logger.error("YouTube search error: %s", e)
        # Fallback: open in default browser
        import webbrowser, urllib.parse
        webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
        return f"Opened YouTube search for '{query}'."


async def play_first_youtube_result(query: str) -> str:
    """Search YouTube and click the first video result."""
    try:
        from browser.browser_engine import get_browser_page
        page = await get_browser_page()
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        # Click first video thumbnail
        await page.wait_for_selector("ytd-video-renderer a#thumbnail", timeout=8000)
        first = page.locator("ytd-video-renderer a#thumbnail").first
        await first.click()
        await page.wait_for_load_state("domcontentloaded")
        title = await page.title()
        return f"Playing: {title}"
    except Exception as e:
        logger.error("YouTube play error: %s", e)
        return await search_youtube(query)


def search_youtube_sync(query: str) -> str:
    """Sync wrapper for use in non-async contexts."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, search_youtube(query))
                return future.result(timeout=20)
        else:
            return loop.run_until_complete(search_youtube(query))
    except Exception as e:
        import webbrowser, urllib.parse
        webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
        return f"Opened YouTube for '{query}'."
