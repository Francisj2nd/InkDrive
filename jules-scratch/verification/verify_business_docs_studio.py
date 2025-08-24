import asyncio
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # 1. Navigate to the Business Docs Studio
            await page.goto("http://127.0.0.1:5001/studio/business", timeout=60000)
            print("Page loaded.")

            # 2. Verify tab switching
            await page.get_by_text("Formal Report", exact=True).click()
            await expect(page.locator("#report")).to_be_visible()
            print("Switched to Formal Report tab successfully.")

            await page.get_by_text("Press Release", exact=True).click()
            await expect(page.locator("#press-release")).to_be_visible()
            print("Switched to Press Release tab successfully.")

            # 3. Switch back to Proposal Writer and fill out the form
            await page.get_by_text("Proposal Writer", exact=True).click()
            await expect(page.locator("#proposal")).to_be_visible()
            print("Switched back to Proposal Writer tab.")

            await page.get_by_label("Your Company").fill("Innovatech Solutions")
            await page.get_by_label("Client Name").fill("Global Exports Co.")
            await page.get_by_label("Client's Problem").fill("Outdated inventory management system leading to stockouts and overstock situations.")
            await page.get_by_label("Proposed Solution").fill("A custom, AI-powered inventory management platform that predicts demand and automates reordering.")
            await page.get_by_label("Deliverables (one per line)").fill("- Phase 1: System analysis and design\n- Phase 2: Platform development and integration\n- Phase 3: Training and rollout")
            await page.get_by_label("Tone").fill("Professional and persuasive")
            print("Form filled out.")

            # 4. Generate content
            await page.get_by_role("button", name="Generate Document").click()

            # 5. Wait for output and take screenshot
            await expect(page.locator(".output-card")).to_be_visible(timeout=60000)
            await expect(page.locator(".output-content")).not_to_be_empty(timeout=30000)
            print("Content generated.")

            await page.screenshot(path="jules-scratch/verification/verification.png")
            print("Screenshot saved.")

        except Exception as e:
            print(f"An error occurred: {e}")
            await page.screenshot(path="jules-scratch/verification/error.png")
        finally:
            await browser.close()

asyncio.run(main())
