# Template source: scrapy + fastapi pattern | Difficulty: medium | Niche: web
from playwright.async_api import async_playwright
from config import PLAYWRIGHT_HEADLESS

async def scrape_url(url: str, selectors: dict) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        page = await browser.new_page()
        # {{SET_USER_AGENT}}
        await page.goto(url, wait_until="networkidle")
        results = {}
        for field, selector in selectors.items():
            try:
                el = await page.query_selector(selector)
                results[field] = await el.inner_text() if el else None
            except Exception:
                results[field] = None
        await browser.close()
        return results
