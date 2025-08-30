import time
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Wait for the app to start
        time.sleep(5)

        # Go to login page and log in
        page.goto("http://localhost:5001/auth/login")
        page.get_by_label("Email").fill("testuser@example.com")
        page.get_by_label("Password").fill("password")
        page.get_by_role("button", name="Sign In").click()
        page.wait_for_load_state("networkidle")

        # Go to the Article Studio
        page.goto("http://localhost:5001/studio/article")
        page.wait_for_load_state("networkidle")

        # Click the 'Dashboard' link and wait for the stats grid to appear
        page.get_by_role("link", name="Dashboard").click()
        expect(page.locator(".stats-grid")).to_be_visible(timeout=10000)

    finally:
        context.close()
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
