# ============================================================
# skills/whatsapp.py — WhatsApp Web Automation
# Strategy: Persistent Playwright profile (no QR every time)
#           + pyautogui fallback on already-open Chrome.
# ============================================================

import logging
import asyncio
import time
import threading
import json
import subprocess
import os
import sys
from pathlib import Path

logger = logging.getLogger("freya.skills.whatsapp")

WA_URL = "https://web.whatsapp.com"

# Persistent profile dir for WhatsApp login (separate from main Chrome profile)
_PROFILE_DIR = str(Path(__file__).parent.parent / "wa_profile")

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"
_config = {}
try:
    with open(_CONFIG_PATH) as f:
        _config = json.load(f)
except Exception:
    pass

CHROME_EXE = _config.get("paths", {}).get(
    "chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)

# ── Core async helper ─────────────────────────────────────────

async def _playwright_send(contact: str, message: str) -> str:
    """Use Playwright with a persistent user profile so login is remembered."""
    from playwright.async_api import async_playwright

    os.makedirs(_PROFILE_DIR, exist_ok=True)
    async with async_playwright() as p:
        # Use bundled Chromium — always works, no Chrome install needed
        # Persistent profile saves WhatsApp login so QR only needed once
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=_PROFILE_DIR,
            headless=False,
            viewport={"width": 1366, "height": 768},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-infobars",
            ],
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        # Navigate to WhatsApp if not already there
        if "web.whatsapp.com" not in page.url:
            await page.goto(WA_URL, wait_until="domcontentloaded", timeout=30000)

        # Wait for chat list (logged in) or QR code
        try:
            await page.wait_for_selector(
                'div[aria-label="Chat list"], canvas[aria-label="Scan me!"]',
                timeout=30000
            )
        except Exception:
            await browser.close()
            return "WhatsApp didn't load. Check internet connection."

        # If QR code is shown → user needs to scan
        if await page.locator('canvas[aria-label="Scan me!"]').count() > 0:
            # Wait up to 60 seconds for user to scan
            logger.info("WhatsApp QR code visible. Waiting for user to scan...")
            try:
                await page.wait_for_selector('div[aria-label="Chat list"]', timeout=60000)
            except Exception:
                await browser.close()
                return "WhatsApp QR scan timed out. Please open WhatsApp Web and scan the QR code first, then try again."

        # WhatsApp is logged in. Search for the contact.
        # Use the new search box approach
        try:
            # Click search icon
            search_btn = page.locator('button[aria-label="Search"]').first
            if await search_btn.count() > 0:
                await search_btn.click()
            else:
                # Try new search box selector
                await page.keyboard.press("Control+f")

            await page.wait_for_timeout(500)

            # Type contact name in search
            search_box = page.locator(
                'div[contenteditable="true"][data-tab="3"], '
                'div[contenteditable="true"][data-testid="chat-list-search"], '
                'input[placeholder="Search or start new chat"]'
            ).first
            await search_box.click()
            await search_box.fill("")
            await page.wait_for_timeout(200)
            await search_box.type(contact, delay=50)
            await page.wait_for_timeout(1500)

            # Try to find the contact in results
            # First try exact title match
            contact_item = page.locator(f'span[title="{contact}"]').first
            if await contact_item.count() == 0:
                # Try partial match
                contact_item = page.locator(f'span[title*="{contact}"]').first
            if await contact_item.count() == 0:
                # Fallback: click first result
                contact_item = page.locator('div[role="listitem"]').first

            await contact_item.click()
            await page.wait_for_timeout(800)

            # Type the message in the message input
            msg_input = page.locator(
                'div[contenteditable="true"][data-tab="10"], '
                'div[contenteditable="true"][data-testid="conversation-compose-box-input"]'
            ).first
            await msg_input.click()
            await page.wait_for_timeout(200)

            # Clear and type message
            await msg_input.fill("")
            await msg_input.type(message, delay=30)
            await page.wait_for_timeout(300)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(800)

            await browser.close()
            return f"Message '{message}' sent to {contact} on WhatsApp!"

        except Exception as e:
            logger.error("WhatsApp send step failed: %s", e)
            await browser.close()
            return f"WhatsApp send failed: {e}"


async def _playwright_open() -> str:
    """Open WhatsApp Web in persistent browser."""
    from playwright.async_api import async_playwright
    os.makedirs(_PROFILE_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=_PROFILE_DIR,
            headless=False,
            viewport={"width": 1366, "height": 768},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-infobars"
            ],
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(WA_URL, wait_until="domcontentloaded", timeout=30000)

        try:
            await page.wait_for_selector(
                'div[aria-label="Chat list"], canvas[aria-label="Scan me!"]',
                timeout=20000
            )
        except Exception:
            pass

        if await page.locator('canvas[aria-label="Scan me!"]').count() > 0:
            # Keep the browser open for QR scan — don't close it
            msg = "WhatsApp Web opened. Please scan the QR code to log in. After scanning once, Freya will remember your login forever!"
            logger.info(msg)
            # Wait for login before closing
            try:
                await page.wait_for_selector('div[aria-label="Chat list"]', timeout=120000)
                await browser.close()
                return "QR scanned successfully! WhatsApp is now logged in and ready."
            except Exception:
                await browser.close()
                return msg
        else:
            await browser.close()
            return "WhatsApp Web is ready and logged in!"


# ── Public sync wrappers ──────────────────────────────────────

def send_message_sync(contact: str, message: str) -> str:
    """Send a WhatsApp message. Runs Playwright in its own thread/loop."""
    try:
        return asyncio.run(_playwright_send(contact, message))
    except RuntimeError:
        # Event loop already running — run in new thread
        result = [None]
        def _run():
            result[0] = asyncio.run(_playwright_send(contact, message))
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=90)
        return result[0] or "WhatsApp message timed out."
    except Exception as e:
        logger.error("send_message_sync error: %s", e)
        return f"WhatsApp error: {e}"


def open_whatsapp_sync() -> str:
    try:
        return asyncio.run(_playwright_open())
    except RuntimeError:
        result = [None]
        def _run():
            result[0] = asyncio.run(_playwright_open())
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=120)
        return result[0] or "WhatsApp opened."
    except Exception as e:
        import webbrowser
        webbrowser.open(WA_URL)
        return "WhatsApp Web opened in browser."


def send_file_sync(contact: str, file_path: str) -> str:
    return "File sending via WhatsApp is coming soon!"


# ── AUTO-CHAT MONITOR ─────────────────────────────────────────

_monitoring = False
_chat_thread = None


def start_auto_chat_sync(contact: str) -> str:
    global _monitoring, _chat_thread
    if _monitoring:
        return "I'm already in chat mode. Say 'stop chatting' first."
    _monitoring = True
    _chat_thread = threading.Thread(
        target=_run_chat_loop, args=(contact,), daemon=True, name="WAChatMonitor"
    )
    _chat_thread.start()
    return f"Chat mode activated with {contact}. I'll reply to their messages automatically. Say 'stop chatting' to stop."


def stop_auto_chat_sync() -> str:
    global _monitoring
    if not _monitoring:
        return "I wasn't in chat mode."
    _monitoring = False
    return "Chat mode deactivated."


def _run_chat_loop(contact: str):
    asyncio.run(_async_chat_loop(contact))


async def _async_chat_loop(contact: str):
    global _monitoring
    from playwright.async_api import async_playwright
    from brain.llm import chat

    os.makedirs(_PROFILE_DIR, exist_ok=True)
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=_PROFILE_DIR,
                headless=False,
                viewport={"width": 1366, "height": 768},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--disable-infobars"
                ],
            )
            page = browser.pages[0] if browser.pages else await browser.new_page()
            await page.goto(WA_URL, wait_until="domcontentloaded", timeout=30000)

            # Wait for login
            try:
                await page.wait_for_selector('div[aria-label="Chat list"]', timeout=60000)
            except Exception:
                logger.error("AutoChat: WhatsApp not logged in.")
                _monitoring = False
                return

            # Open contact chat
            search_box = page.locator('div[contenteditable="true"][data-tab="3"]').first
            await search_box.click()
            await search_box.type(contact, delay=50)
            await page.wait_for_timeout(1500)
            contact_item = page.locator(f'span[title*="{contact}"]').first
            if await contact_item.count() == 0:
                contact_item = page.locator('div[role="listitem"]').first
            await contact_item.click()
            await page.wait_for_timeout(1000)

            last_msg = ""
            logger.info("AutoChat: Monitoring chat with %s", contact)

            while _monitoring:
                try:
                    msgs = await page.locator('div.message-in span.selectable-text').all_inner_texts()
                    if msgs:
                        latest = msgs[-1].strip()
                        if latest and latest != last_msg:
                            last_msg = latest
                            logger.info("AutoChat: New message: %s", latest)
                            reply = chat(
                                user_message=f"Reply to this WhatsApp message from {contact}: '{latest}'. Be short, casual, friendly.",
                                system_prompt="You are chatting on WhatsApp on behalf of Atharv. Keep replies very short, natural, and human. Max 2 sentences.",
                                history=[]
                            )
                            msg_input = page.locator('div[contenteditable="true"][data-tab="10"]').first
                            await msg_input.click()
                            await msg_input.type(reply, delay=30)
                            await page.keyboard.press("Enter")
                            logger.info("AutoChat: Replied: %s", reply)
                except Exception as e:
                    logger.debug("AutoChat loop: %s", e)
                await asyncio.sleep(3)

            await browser.close()
    except Exception as e:
        logger.error("AutoChat error: %s", e)
    finally:
        _monitoring = False