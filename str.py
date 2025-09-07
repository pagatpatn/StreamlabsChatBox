import os
import asyncio
import requests
import time
from playwright.async_api import async_playwright

# ================= CONFIG =================
CHAT_URL = os.getenv("CHAT_URL")  # replace with your widget
NTFY_URL = os.getenv("NTFY_URL") # replace with your ntfy topic
SEND_DELAY = 5
DEDUP_WINDOW = 5
MAX_LEN = 123

recent_msgs = {}
send_queue = asyncio.Queue()

# ---------- Enqueue messages ----------
async def enqueue_message(platform: str, user: str, message: str):
    now = time.time()
    key = f"{platform}:{user}:{message}"
    if key in recent_msgs and now - recent_msgs[key] < DEDUP_WINDOW:
        return
    recent_msgs[key] = now
    for k in list(recent_msgs.keys()):
        if now - recent_msgs[k] > DEDUP_WINDOW:
            del recent_msgs[k]
    chunks = [message[i:i+MAX_LEN] for i in range(0, len(message), MAX_LEN)] if len(message) > MAX_LEN else [message]
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        suffix = f" [{idx}/{total}]" if total > 1 else ""
        await send_queue.put((platform, user, chunk + suffix))

# ---------- Worker for ntfy ----------
async def ntfy_worker():
    while True:
        platform, user, msg = await send_queue.get()
        try:
            await asyncio.to_thread(
                requests.post,
                NTFY_URL,
                data=msg.encode("utf-8"),
                headers={"Title": f"[{platform}] {user}"}
            )
            print(f"✅ Sent: [{platform}] {user}: {msg}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        await asyncio.sleep(SEND_DELAY)
        send_queue.task_done()

# ---------- Browser observer ----------
async def run_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # must be True in cloud
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-accelerated-2d-canvas",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto(CHAT_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector("#log", timeout=30000)
        except Exception:
            print("❌ #log not found. Widget might not have loaded.")
        print("📡 Chat widget loaded — attaching observer...")

        async def on_new_message(_source, payload):
            user = payload.get("user", "Unknown")
            message = payload.get("message", "")
            platform = payload.get("platform", "Unknown")
            if message and message.strip():
                await enqueue_message(platform, user, message)

        await page.expose_binding("onNewMessage", on_new_message)

        # Inject JS to capture messages
        await page.evaluate(
            """
            (() => {
                function extractMessage(node) {
                    if (!node) return '';
                    const parts = [];
                    node.childNodes.forEach(child => {
                        if (child.nodeType === Node.TEXT_NODE) parts.push(child.textContent);
                        else if (child.nodeType === 1) {
                            if (child.classList && child.classList.contains('emote')) {
                                const img = child.querySelector('img');
                                if (img) parts.push(img.alt || ':EMOTE:');
                            } else parts.push(child.textContent || '');
                        }
                    });
                    return parts.join('').trim();
                }

                function detectPlatform(node) {
                    if (node.querySelector("img.platform-icon[src*='kick']")) return "Kick";
                    if (node.querySelector("img.platform-icon[src*='youtube']")) return "YouTube";
                    if (node.querySelector("img.platform-icon[src*='twitch']")) return "Twitch";
                    if (node.querySelector("img.platform-icon[src*='facebook']")) return "Facebook";
                    return "Unknown";
                }

                function processNode(node) {
                    if (!node || node.nodeType !== 1 || !node.dataset || !node.dataset.from) return;
                    const user = node.dataset.from;
                    const msgNode = node.querySelector('.message');
                    const msg = extractMessage(msgNode);
                    const platform = detectPlatform(node);
                    if (msg) window.onNewMessage({user, message: msg, platform});
                }

                const log = document.querySelector('#log');
                if (!log) { console.log('#log not found'); return; }

                log.querySelectorAll('div[data-from]').forEach(processNode);
                new MutationObserver(muts => muts.forEach(m => m.addedNodes.forEach(processNode)))
                    .observe(log, { childList: true });
                console.log('✅ Chat observer attached');
            })();
            """
        )

        await asyncio.Future()  # keep page running

# ---------- main ----------
async def main():
    worker = asyncio.create_task(ntfy_worker())
    try:
        await run_browser()
    finally:
        worker.cancel()

if __name__ == "__main__":
    asyncio.run(main())
