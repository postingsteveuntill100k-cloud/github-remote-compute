from playwright.sync_api import sync_playwright

def run_cuj(page):
    page.goto("http://localhost:45413") # we will sed this
    page.wait_for_timeout(1000)

    # Click forgot password without email
    page.get_by_text("Forgot Password?").click()
    page.wait_for_timeout(1000)
    page.screenshot(path="/home/jules/verification/screenshots/verification_forgot_error.png", full_page=True)

    # Click forgot password with email
    page.get_by_placeholder("name@company.com").fill("test@example.com")
    page.wait_for_timeout(500)
    page.get_by_text("Forgot Password?").click()
    page.wait_for_timeout(2000)
    page.screenshot(path="/home/jules/verification/screenshots/verification_forgot_success.png", full_page=True)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="/home/jules/verification/videos",
        )
        page = context.new_page()
        try:
            run_cuj(page)
        finally:
            context.close()
            browser.close()
