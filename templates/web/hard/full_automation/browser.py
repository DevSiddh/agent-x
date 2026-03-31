# Template source: seleniumbase/seleniumbase | Difficulty: hard | Niche: web
from playwright.async_api import async_playwright
import random
from config import PROXY_LIST, USER_AGENTS, STEALTH_MODE

async def get_browser(proxy: str = None):
    p = await async_playwright().start()
    proxy_cfg = {"server": proxy} if proxy else None
    browser = await p.chromium.launch(
        headless=True,
        proxy=proxy_cfg,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
    )
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        locale="en-US",
        timezone_id="America/New_York",
        # {{ADD_FINGERPRINT_PARAMS}}
    )
    if STEALTH_MODE:
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // {{ADD_MORE_STEALTH_SCRIPTS}}
        """)
    return browser, context

async def rotate_proxy() -> str:
    return random.choice(PROXY_LIST)
