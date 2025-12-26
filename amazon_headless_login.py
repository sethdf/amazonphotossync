#!/usr/bin/env python3
"""
Headless Amazon Photos Login

Authenticates to Amazon Photos without a visible browser window.
Handles email, password, and OTP (if 2FA is enabled).

Usage:
  python amazon_headless_login.py

Environment variables (optional):
  AMAZON_EMAIL - Amazon account email
  AMAZON_PASSWORD - Amazon account password
"""

import asyncio
import getpass
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

SESSION_FILE = "amazon_session"


async def main():
    print("=" * 60)
    print("Amazon Photos Headless Login")
    print("=" * 60)
    print()

    # Get credentials
    email = os.environ.get('AMAZON_EMAIL')
    password = os.environ.get('AMAZON_PASSWORD')

    if not email:
        email = input("Amazon Email: ").strip()
    if not password:
        password = getpass.getpass("Amazon Password: ")

    if not email or not password:
        print("Error: Email and password are required")
        sys.exit(1)

    print()
    print("Launching headless browser...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Navigate to Amazon Photos
            print("Navigating to Amazon Photos...")
            await page.goto("https://www.amazon.com/photos", timeout=30000)
            await page.wait_for_timeout(2000)

            # Check if already logged in
            if "amazon.com/photos" in page.url and "ap/signin" not in page.url:
                # Check for sign-in button
                sign_in_button = await page.query_selector('a[href*="signin"], button:has-text("Sign in")')
                if sign_in_button:
                    print("Clicking sign in...")
                    await sign_in_button.click()
                    await page.wait_for_timeout(2000)

            # Wait for and fill email
            print("Entering email...")
            email_field = await page.wait_for_selector('input[type="email"], input[name="email"], #ap_email', timeout=10000)
            await email_field.fill(email)

            # Click continue/next if present
            continue_btn = await page.query_selector('#continue, input[type="submit"], button[type="submit"]')
            if continue_btn:
                await continue_btn.click()
                await page.wait_for_timeout(2000)

            # Wait for and fill password
            print("Entering password...")
            password_field = await page.wait_for_selector('input[type="password"], input[name="password"], #ap_password', timeout=10000)
            await password_field.fill(password)

            # Click sign in
            sign_in_btn = await page.query_selector('#signInSubmit, input[type="submit"], button[type="submit"]')
            if sign_in_btn:
                await sign_in_btn.click()
                await page.wait_for_timeout(3000)

            # Check for OTP/2FA
            otp_field = await page.query_selector('input[name="otpCode"], input[name="code"], #auth-mfa-otpcode')
            if otp_field:
                print()
                print("=" * 60)
                print("Two-Factor Authentication Required")
                print("=" * 60)
                otp_code = input("Enter OTP code from your authenticator app: ").strip()

                await otp_field.fill(otp_code)

                # Check for "remember device" checkbox
                remember_checkbox = await page.query_selector('input[name="rememberDevice"]')
                if remember_checkbox:
                    await remember_checkbox.check()

                # Submit OTP
                submit_btn = await page.query_selector('#auth-signin-button, input[type="submit"], button[type="submit"]')
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_timeout(3000)

            # Check for CAPTCHA
            captcha = await page.query_selector('img[src*="captcha"], #auth-captcha-image')
            if captcha:
                print()
                print("=" * 60)
                print("CAPTCHA Required")
                print("=" * 60)
                print("Unfortunately, Amazon is showing a CAPTCHA.")
                print("You may need to:")
                print("  1. Try again later")
                print("  2. Use a different network")
                print("  3. Use the GUI login script with X11 forwarding")
                await browser.close()
                sys.exit(1)

            # Check for approval request (new device)
            approval_msg = await page.query_selector('text="Approve the notification"')
            if approval_msg:
                print()
                print("=" * 60)
                print("Device Approval Required")
                print("=" * 60)
                print("Amazon sent a push notification to your phone.")
                print("Please approve the login request, then press Enter.")
                input("Press Enter after approving...")
                await page.wait_for_timeout(5000)

            # Navigate to photos to confirm login
            print("Verifying login...")
            await page.goto("https://www.amazon.com/photos/all", timeout=30000)
            await page.wait_for_timeout(3000)

            # Check if we're logged in
            current_url = page.url
            if "signin" in current_url or "ap/signin" in current_url:
                print()
                print("ERROR: Login failed. Still on sign-in page.")
                print(f"Current URL: {current_url}")

                # Take screenshot for debugging
                await page.screenshot(path="login_failed.png")
                print("Screenshot saved to: login_failed.png")
                await browser.close()
                sys.exit(1)

            # Save session
            print("Saving session...")
            await context.storage_state(path=SESSION_FILE)

            print()
            print("=" * 60)
            print("SUCCESS! Session saved to:", SESSION_FILE)
            print("=" * 60)
            print()
            print("You can now run:")
            print("  python amazon_photos_sync.py enumerate --full")
            print("  python amazon_photos_sync.py download")

        except Exception as e:
            print(f"\nError during login: {e}")

            # Take screenshot for debugging
            try:
                await page.screenshot(path="login_error.png")
                print("Screenshot saved to: login_error.png")
            except:
                pass

            await browser.close()
            sys.exit(1)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
