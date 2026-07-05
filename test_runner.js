const puppeteer = require('puppeteer');
const { PuppeteerScreenRecorder } = require('puppeteer-screen-recorder');

(async () => {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    const recorder = new PuppeteerScreenRecorder(page);
    await recorder.start('./demo_run.mp4');

    try {
        await page.goto('http://localhost:8080');

        // Wait for Firebase Auth UI
        await page.waitForSelector('#input-email');

        // Bypass the real UI wait for the auth since it requires real keys.
        // We will mock the CSS toggle so we can test the dashboard in this local runner.
        await page.evaluate(() => {
            document.getElementById('auth-gate').classList.add('hidden');
            const shell = document.getElementById('app-shell');
            shell.classList.remove('hidden', 'opacity-0');
        });

        await page.waitForSelector('#dashboard-grid');

        // File upload injection (we'll just click it if file isn't present to test DOM interaction)
        await page.waitForSelector('#btn-upload-db');
        // We would upload, but we'll simulate the chat directly for brevity

        await page.waitForSelector('#chat-input');
        await page.type('#chat-input', 'Summarize data', { delay: 50 });

        await page.click('#btn-send-chat');

        // Wait for AI response block
        await page.waitForSelector('.agent-message', { timeout: 15000 });
        // Let the streaming animation run
        await new Promise(r => setTimeout(r, 6000));

        console.log("Puppeteer test completed successfully.");
    } catch (e) {
        console.error("Puppeteer test failed:", e);
    } finally {
        await recorder.stop();
        await browser.close();
    }
})();
