import asyncio
import requests
import time
from playwright.async_api import async_playwright

# ================= CONFIG =================
CHAT_URL = "https://streamlabs.com/widgets/chat-box/v1/YOUR_WIDGET_ID"  # replace with your widget
NTFY_URL = "https://ntfy.sh/streamchats123"  # replace with your ntfy topic
SEND_DELAY = 5          # seconds between sending each queued message
DEDUP_WINDOW = 5        # seconds to suppress duplicate messages
MAX_LEN = 123           # chunk length before splitting

# simple dedup store and send queue
recent_msgs = {}        # { key: timestamp }
send_queue = asyncio.Queue()


# ---------- Enqueue (with dedup + splitting) ----------
async def enqueue_message(platform: str, user: str, message: str):
    now = time.time()
    key = f"{platform}:{user}:{message}"
    if key in recent_msgs and now - recent_msgs[key] < DEDUP_WINDOW:
        return
    recent_msgs[key] = now

    for k in list(recent_msgs.keys()):
        if now - recent_msgs[k] > DEDUP_WINDOW:
            del recent_msgs[k]

    if len(message) <= MAX_LEN:
        chunks = [message]
    else:
        chunks = [message[i:i+MAX_LEN] for i in range(0, len(message), MAX_LEN)]

    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        suffix = f" [{idx}/{total}]" if total > 1 else ""
        await send_queue.put((platform, user, chunk + suffix))


# ---------- Worker ----------
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
            print(f"✅ Sent to ntfy: [{platform}] {user}: {msg}")
        except Exception as e:
            print(f"❌ Failed to send to ntfy: {e}")
        await asyncio.sleep(SEND_DELAY)
        send_queue.task_done()


# ---------- Browser ----------
async def run_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-software-rasterizer",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-accelerated-2d-canvas",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = await browser.new_page()
        await page.goto(CHAT_URL, wait_until="domcontentloaded")

        try:
            await page.wait_for_selector("#log", timeout=30000)
        except Exception:
            print("❌ #log not found; widget may not have loaded.")

        print("📡 Chat widget loaded — attaching observer...")

        async def on_new_message(_source, payload):
            user = payload.get("user", "Unknown")
            message = payload.get("message", "")
            platform = payload.get("platform", "Facebook")
            if message.strip():
                await enqueue_message(platform, user, message)

        await page.expose_binding("onNewMessage", on_new_message)

        await page.evaluate(
            """
            (() => {
                function extractMessage(node) {
                    if (!node) return '';
                    const parts = [];
                    node.childNodes.forEach(child => {
                        if (child.nodeType === Node.TEXT_NODE) {
                            parts.push(child.textContent);
                        } else if (child.nodeType === 1) {
                            if (child.classList.contains('emote')) {
                                const img = child.querySelector('img') || child;
                                if (img) {
                                    let alt = (img.alt || '').trim();
                                    if (alt) {
                                        parts.push(alt);
                                    } else {
                                        let fname = (img.src || '').split('/').pop().split('?')[0];
                                        fname = fname.split('.')[0];
                                        if (fname.toLowerCase() === 'fullsize') {
                                            parts.push(':KEKW:');
                                        } else {
                                            parts.push(':' + fname.toUpperCase() + ':');
                                        }
                                    }
                                }
                            } else {
                                parts.push(child.textContent || '');
                            }
                        }
                    });
                    return parts.join('').trim();
                }

                function detectPlatform(node) {
                    if (node.querySelector("img.platform-icon[src*='kick']")) return "Kick";
                    if (node.querySelector("img.platform-icon[src*='youtube']")) return "YouTube";
                    if (node.querySelector("img.platform-icon[src*='twitch']")) return "Twitch";
                    if (node.querySelector("img.platform-icon[src*='facebook']")) return "Facebook";
                    return "Facebook";
                }

                function processNode(node) {
                    if (!node || !node.dataset || !node.dataset.from) return;
                    const user = node.dataset.from;
                    const msgNode = node.querySelector('.message');
                    const msg = extractMessage(msgNode);
                    const platform = detectPlatform(node);
                    if (msg) window.onNewMessage({user, message: msg, platform});
                }

                const log = document.querySelector('#log');
                if (!log) return;

                log.querySelectorAll('div[data-from]').forEach(processNode);

                const observer = new MutationObserver(muts => {
                    for (const m of muts) {
                        for (const n of m.addedNodes) {
                            processNode(n);
                        }
                    }
                });
                observer.observe(log, { childList: true });
                console.log('✅ Chat observer attached');
            })();
            """
        )

        await asyncio.Future()


# ---------- Main ----------
async def main():
    worker = asyncio.create_task(ntfy_worker())
    try:
        await run_browser()
    finally:
        worker.cancel()


if __name__ == "__main__":
    asyncio.run(main())
