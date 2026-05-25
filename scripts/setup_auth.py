"""Manually log into target apps and save Playwright browser auth state."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright
from shared import config


async def setup_auth():
    Path(config.AUTH_STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://login.salesforce.com")
        input("Log in to Salesforce, then press Enter to continue...")

        await page.goto("https://mail.google.com")
        input("Log in to Gmail, then press Enter to continue...")

        await context.storage_state(path=config.AUTH_STATE_PATH)
        print(f"Auth state saved to {config.AUTH_STATE_PATH}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(setup_auth())
