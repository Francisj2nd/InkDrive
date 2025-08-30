import time
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Wait for the app to start
        time.sleep(5)

        # Use the temporary login route
        page.goto("http://localhost:5001/auth/temp_login")
        page.wait_for_load_state("networkidle")

        # Go to the Article Studio
        page.goto("http://localhost:5001/studio/article")

        # Take a screenshot to verify the toggle button's alignment
        page.screenshot(path="jules-scratch/verification/article_studio_ui_fixed.png")

        # Click the 'Dashboard' link
        page.get_by_role("link", name="Dashboard").click()

        # Wait for the dashboard content to appear
        expect(page.locator(".stats-grid")).to_be_visible(timeout=10000)

        # Take a second screenshot of the dashboard view
        page.screenshot(path="jules-scratch/verification/article_studio_dashboard.png")

    finally:
        context.close()
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
