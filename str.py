import os
import asyncio
import requests
import time
from playwright.async_api import async_playwright

# ================= CONFIG =================
CHAT_URL = "https://streamlabs.com/widgets/chat-box/v1/C6DC1A891DE65F9C4C81C602868ED61C59018D9968330B8B781FA78E095E4A00589BCD3A6BF64B604F9742C6F0B84CCC38884FE4523AC3FFE45812E581444282E462DB432308C0D969F72078093D6B2CFBB49DA03E30676954BB802F25B748ED1208B0E76480F15014408FA3F09FED292ECA427F16820E876BD961E69A"
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh/streamchats123")
  # put your ntfy topic here
SEND_DELAY = 5          # seconds between sending each queued message
DEDUP_WINDOW = 5        # seconds to suppress duplicate messages
MAX_LEN = 123           # chunk length before splitting

# simple dedup store and send queue
recent_msgs = {}        # { key: timestamp }
send_queue = asyncio.Queue()


# ---------- Enqueue (with dedup + splitting) ----------
async def enqueue_message(platform: str, user: str, message: str):
    """Check dedup then split message into chunks and enqueue them."""
    now = time.time()
    key = f"{platform}:{user}:{message}"
    # dedup by time window
    if key in recent_msgs and now - recent_msgs[key] < DEDUP_WINDOW:
        # skip duplicate
        return
    recent_msgs[key] = now

    # cleanup old dedup entries
    for k in list(recent_msgs.keys()):
        if now - recent_msgs[k] > DEDUP_WINDOW:
            del recent_msgs[k]

    # split long messages
    if len(message) <= MAX_LEN:
        chunks = [message]
    else:
        chunks = [message[i:i+MAX_LEN] for i in range(0, len(message), MAX_LEN)]

    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        suffix = f" [{idx}/{total}]" if total > 1 else ""
        await send_queue.put((platform, user, chunk + suffix))


# ---------- Worker that actually POSTs to ntfy (rate-limited) ----------
async def ntfy_worker():
    while True:
        platform, user, msg = await send_queue.get()
        try:
            # run blocking requests.post off the event loop
            await asyncio.to_thread(
                requests.post,
                NTFY_URL,
                data=msg.encode("utf-8"),
                headers={"Title": f"[{platform}] {user}"}
            )
            print(f"✅ Sent to ntfy: [{platform}] {user}: {msg}")
        except Exception as e:
            print(f"❌ Failed to send to ntfy: {e}")
        # global send delay between every queued message
        await asyncio.sleep(SEND_DELAY)
        send_queue.task_done()


# ---------- Browser + DOM observer ----------
async def run_browser():
    async with async_playwright() as p:
        # Stealth headful rendering off-screen so Kick renders but you don't see a window
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--window-position=-32000,-32000",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-software-rasterizer",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-accelerated-2d-canvas",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = await browser.new_page()
        # optional: set viewport size to something wide so widget renders properly
        await page.set_viewport_size({"width": 1280, "height": 800})

        await page.goto(CHAT_URL, wait_until="domcontentloaded")

        # wait for #log to appear (gives time for widget to initialize)
        try:
            await page.wait_for_selector("#log", timeout=30000)
        except Exception:
            print("❌ #log not found within timeout; widget might not have loaded.")
            # keep running for debugging or exit
            # await browser.close()
            # return

        print("📡 Chat widget loaded — attaching observer...")

        # binding callback that the page will call
        async def on_new_message(_source, payload):
            # payload is expected to be dict: { user, message, platform }
            user = payload.get("user", "Unknown")
            message = payload.get("message", "")
            platform = payload.get("platform", "Facebook")
            if message and message.strip():
                await enqueue_message(platform, user, message)

        await page.expose_binding("onNewMessage", on_new_message)

        # Inject JS (IIFE) — extracts text + custom emotes fallback to [NAME]
        await page.evaluate(
            """
            (() => {
                function safeNameFromUrl(url) {
                    try {
                        const last = url.split('/').pop().split('?')[0];
                        const base = last.split('.')[0] || 'EMOTE';
                        return base.replace(/[^a-zA-Z0-9_-]+/g, '');
                    } catch (e) {
                        return 'EMOTE';
                    }
                }

                function extractMessage(node) {
    if (!node) return '';
    const parts = [];
    node.childNodes.forEach(child => {
        if (child.nodeType === Node.TEXT_NODE) {
            parts.push(child.textContent);
        } else if (child.nodeType === 1) {
            if (child.classList && child.classList.contains('emote')) {
                const img = child.querySelector('img');
                if (img) {
                    let alt = (img.alt || '').trim();
                    if (alt) {
                        parts.push(alt);  // YouTube/Twitch/FB usually have this
                    } else {
                        // Fallback: derive from filename
                        let fname = (img.src || '').split('/').pop().split('?')[0];
                        fname = fname.split('.')[0];  // remove extension
                        if (fname.toLowerCase() === 'fullsize') {
                            // Kick sometimes uses "fullsize.png" – replace with :EMOTE:
                            parts.push(':KEKW:');  // default fallback if no better info
                        } else {
                            parts.push(':' + fname.toUpperCase() + ':');
                        }
                    }
                }
            } else if (child.tagName === 'IMG' && child.classList.contains('emote')) {
                const img = child;
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
            } else {
                parts.push(child.textContent || '');
            }
        }
    });
    return parts.join('').trim();
}

                function detectPlatform(node) {
                    // look for platform icon inside the message row
                    if (node.querySelector("img.platform-icon[src*='kick']")) return "Kick";
                    if (node.querySelector("img.platform-icon[src*='youtube']")) return "YouTube";
                    if (node.querySelector("img.platform-icon[src*='twitch']")) return "Twitch";
                    if (node.querySelector("img.platform-icon[src*='facebook']")) return "Facebook";
                    return "Facebook"; // safe default
                }

                function processNode(node) {
                    try {
                        if (!node || node.nodeType !== 1 || !node.dataset || !node.dataset.from) return;
                        const user = node.dataset.from;
                        const msgNode = node.querySelector('.message');
                        const msg = extractMessage(msgNode);
                        const platform = detectPlatform(node);
                        if (msg) window.onNewMessage({user: user, message: msg, platform: platform});
                    } catch (e) {
                        // ignore per-message errors
                    }
                }

                const log = document.querySelector('#log');
                if (!log) {
                    console.log('#log not found');
                    return;
                }

                // capture existing messages immediately (incl. first)
                log.querySelectorAll('div[data-from]').forEach(processNode);

                // observe new messages
                const observer = new MutationObserver(muts => {
                    for (const m of muts) {
                        for (const n of m.addedNodes) {
                            processNode(n);
                        }
                    }
                });
                observer.observe(log, { childList: true });
                console.log('✅ Chat observer attached (with emote fallback)');
            })();
            """
        )

        # keep page running
        await asyncio.Future()


# ---------- main ----------
async def main():
    # start ntfy worker
    worker = asyncio.create_task(ntfy_worker())
    # start browser (this blocks indefinitely)
    try:
        await run_browser()
    finally:
        worker.cancel()


if __name__ == "__main__":
    asyncio.run(main())
