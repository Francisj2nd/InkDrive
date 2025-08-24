from playwright.sync_api import sync_playwright, expect, TimeoutError
import sys

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        email = "testuser@example.com"
        password = "password"
        name = "Test User"

        try:
            # --- Registration/Login Flow ---
            page.goto("http://127.0.0.1:5001/auth/register")
            page.locator('input[name="email"]').fill(email)
            page.locator('input[name="name"]').fill(name)
            page.locator('input[name="password"]').fill(password)
            page.locator('input[name="password2"]').fill(password)
            page.click('button[type="submit"]')

            try:
                # On successful registration, we are redirected to the dashboard
                page.wait_for_url("http://127.0.0.1:5001/", timeout=5000)
            except TimeoutError:
                # If redirection doesn't happen, it's likely because the user already exists.
                # We'll proceed to login.
                page.goto("http://127.0.0.1:5001/auth/login")
                page.locator('input[name="email"]').fill(email)
                page.locator('input[name="password"]').fill(password)
                page.click('button[type="submit"]')
                page.wait_for_url("http://127.0.0.1:5001/")

            # Now we must be logged in and at the dashboard.
            expect(page).to_have_url("http://127.0.0.1:5001/")

            # --- Test Execution ---
            page.goto("http://127.0.0.1:5001/studio/business")
            page.wait_for_load_state()

            page.click('button[data-tab="proposal"]')

            long_text = "This is a very long text to ensure that the output area will need to be scrollable. " * 100
            page.locator('input[id="prop-company"]').fill("Jules' Engineering")
            page.locator('input[id="prop-client"]').fill("Test Client")
            page.locator('textarea[id="prop-problem"]').fill(long_text)
            page.locator('textarea[id="prop-solution"]').fill("A solution.")
            page.locator('textarea[id="prop-deliverables"]').fill("Deliverables.")

            page.click('button[id="generateBtn"]')

            page.wait_for_selector("#business-output-display .output-card", timeout=60000)

            page.screenshot(path="jules-scratch/verification/scrolling_verification.png")

        except Exception as e:
            page.screenshot(path="jules-scratch/verification/error.png")
            print(f"An error occurred: {e}")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()
