#!/usr/bin/env python3
"""
Simple session saver - opens browser, waits 60 seconds, saves session.
"""

import asyncio
from playwright.async_api import async_playwright

async def main():
    print("Opening browser - you have 60 seconds to log in...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--no-sandbox'])
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        await page.goto("https://www.amazon.com/photos")

        # Wait 60 seconds for user to log in
        for i in range(60, 0, -10):
            print(f"  {i} seconds remaining...")
            await page.wait_for_timeout(10000)

        print("\nSaving session...")
        await context.storage_state(path="amazon_session")
        await page.screenshot(path="session_screenshot.png")
        print("Session saved to: amazon_session")
        print("Screenshot saved to: session_screenshot.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
