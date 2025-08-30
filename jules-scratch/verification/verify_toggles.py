import time
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Wait for the app to start
        time.sleep(5)

        # Log in as super admin
        page.goto("http://localhost:5001/auth/login")

        try:
            page.get_by_label("Email").fill("superadmin@example.com")
            page.get_by_label("Password").fill("password")
            page.get_by_role("button", name="Sign In").click()
            page.wait_for_url("http://localhost:5001/")
        except Exception as e:
            print("Error during login:")
            print(page.content())
            raise e

        # Go to the Article Studio
        page.goto("http://localhost:5001/studio/article")

        # Take a screenshot
        page.screenshot(path="jules-scratch/verification/article_studio_toggles.png")

    finally:
        context.close()
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
