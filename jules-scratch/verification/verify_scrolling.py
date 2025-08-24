from playwright.sync_api import sync_playwright, expect
import time

def run_final_final_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # --- 1. Register a new user ---
            print("Navigating to registration page...")
            page.goto("http://127.0.0.1:5001/auth/register", timeout=60000)

            email = f"tester_{int(time.time())}@example.com"
            password = "password123"

            print(f"Registering with email: {email}")
            page.get_by_label("Full Name").fill("Tester")
            page.get_by_label("Email").fill(email)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_label("Confirm Password").fill(password)
            page.get_by_role("button", name="Create Account").click()

            print("Waiting for redirection to dashboard...")
            expect(page).to_have_url("http://127.0.0.1:5001/", timeout=20000)
            print("Registration and login successful.")

            # --- 2. Navigate to the Studio ---
            print("Navigating to Article Studio...")
            page.goto("http://127.0.0.1:5001/studio/article", timeout=60000)

            # --- 3. Generate Content with CORRECT label ---
            print("Generating article content...")
            topic_input = page.get_by_label("Topic")
            expect(topic_input).to_be_visible(timeout=10000)
            topic_input.fill("An in-depth history of the internet, from ARPANET to the modern web, covering key milestones, technologies, and influential figures. The story should be long enough to require scrolling on a standard 1080p screen.")

            generate_button = page.get_by_role("button", name="Generate Article")
            generate_button.click()

            # --- 4. Wait for Output, Scroll, and Take Screenshot ---
            print("Waiting for generated content...")
            output_area = page.locator(".studio-output")
            expect(output_area.locator(".article-content h1")).to_be_visible(timeout=120000)
            print("Content generated. Preparing to scroll and screenshot.")

            initial_scroll_top = output_area.evaluate("node => node.scrollTop")
            output_area.evaluate("node => node.scrollTop = node.scrollHeight")
            time.sleep(1) # Wait for render
            final_scroll_top = output_area.evaluate("node => node.scrollTop")

            if final_scroll_top <= initial_scroll_top:
                raise Exception("Scrolling failed. The output panel did not scroll.")

            page.screenshot(path="jules-scratch/verification/scrolling_fix_verification.png")
            print("Successfully generated article, scrolled output, and took screenshot.")

        except Exception as e:
            print(f"An error occurred: {e}")
            page.screenshot(path="jules-scratch/verification/error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run_final_final_verification()
