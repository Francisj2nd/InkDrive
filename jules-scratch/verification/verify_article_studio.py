import re
import time
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Wait for the app to start
        time.sleep(5)

        # 1. Log in as a regular user
        page.goto("http://localhost:5001/auth/login")
        page.get_by_label("Email").fill("testuser@example.com")
        page.get_by_label("Password").fill("password")
        page.get_by_role("button", name="Sign In").click()
        page.wait_for_url("http://localhost:5001/")


        # 2. Go to the Article Studio
        page.goto("http://localhost:5001/studio/article")

        # 3. Check for absence of "My Articles"
        sidebar = page.locator(".sidebar")
        expect(sidebar).not_to_contain_text("My Articles")

        # 4. Check for absence of "Publish" button
        # This button only appears after generating an article, so we need to generate one first.
        page.get_by_label("Topic").fill("Test Topic")
        page.get_by_role("button", name="Generate Article").click()

        # Wait for the article to be generated
        expect(page.locator(".article-content")).to_be_visible(timeout=60000)

        # Now check that the publish button is not there
        expect(page.locator("#publishBtn")).not_to_be_visible()

        # 5. Check for "New Article" button
        expect(page.get_by_role("button", name="New Article")).to_be_visible()

        # 6. Take a screenshot
        page.screenshot(path="jules-scratch/verification/regular_user_view.png")

        # 7. Check that the image toggle is not visible
        expect(page.locator("#imageToggle")).not_to_be_visible()

        # 8. Log out
        page.get_by_role("link", name="Logout").click()
        page.wait_for_url("http://localhost:5001/")


        # 9. Log in as super admin
        page.goto("http://localhost:5001/auth/login")
        page.get_by_label("Email").fill("superadmin@example.com")
        page.get_by_label("Password").fill("password")
        page.get_by_role("button", name="Sign In").click()
        page.wait_for_url("http://localhost:5001/")

        # 10. Go to the Article Studio
        page.goto("http://localhost:5001/studio/article")

        # 11. Check that the image toggle is visible
        expect(page.locator("#imageToggle")).to_be_visible()

        # 12. Take another screenshot
        page.screenshot(path="jules-scratch/verification/super_admin_view.png")
    finally:
        context.close()
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
