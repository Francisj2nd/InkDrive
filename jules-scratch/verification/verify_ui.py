import time
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # Wait for the app to start
        time.sleep(5)

        # Go to the Article Studio
        page.goto("http://localhost:5001/studio/article")

        # Take a screenshot
        page.screenshot(path="jules-scratch/verification/article_studio_ui.png")

    finally:
        context.close()
        browser.close()

with sync_playwright() as playwright:
    run(playwright)
