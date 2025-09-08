import asyncio
import requests
import time
from playwright.async_api import async_playwright


# ================= CONFIG =================
CHAT_URL = "https://streamlabs.com/widgets/chat-box/v1/C6DC1A891DE65F9C4C81C602868ED61C59018D9968330B8B781FA78E095E4A00589BCD3A6BF64B604F9742C6F0B84CCC38884FE4523AC3FFE45812E581444282E462DB432308C0D969F72078093D6B2CFBB49DA03E30676954BB802F25B748ED1208B0E76480F15014408FA3F09FED292ECA427F16820E876BD961E69A"
NTFY_URL = "https://ntfy.sh/streamchats123"  # put your ntfy topic here
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


# ---------- Worker that actually POSTs to ntfy ----------
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


# ---------- Browser + DOM observer ----------
async def run_browser():
    async with async_playwright() as p:
        # Headless mode for Railway
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto(CHAT_URL, wait_until="domcontentloaded")

        try:
            await page.wait_for_selector("#log", timeout=30000)
        except Exception:
            print("❌ #log not found within timeout; widget might not have loaded.")

        print("📡 Chat widget loaded — attaching observer...")

        async def on_new_message(_source, payload):
            user = payload.get("user", "Unknown")
            message = payload.get("message", "")
            platform = payload.get("platform", "Facebook")
            if message and message.strip():
                await enqueue_message(platform, user, message)

        await page.expose_binding("onNewMessage", on_new_message)

        # ---------------- JS injection ----------------
        await page.evaluate(
            """
            (() => {
                function safeNameFromUrl(url) {
                    try {
                        const last = url.split('/').pop().split('?')[0];
                        const base = last.split('.')[0] || 'EMOTE';
                        return base.replace(/[^a-zA-Z0-9_-]+/g, '');
                    } catch (e) { return 'EMOTE'; }
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
                                    if (alt) { parts.push(alt); }
                                    else { parts.push(':KEKW:'); }
                                }
                            } else {
                                parts.push(child.textContent || '');
                            }
                        }
                    });
                    return parts.join('').trim();
                }

                // ===== MODIFIED: detect Kick reliably =====
                function detectPlatform(node) {
                    if (node.querySelector("img.platform-icon[src*='kick']")) return "Kick";
                    if (node.querySelector("img.platform-icon[src*='youtube']")) return "YouTube";
                    if (node.querySelector("img.platform-icon[src*='twitch']")) return "Twitch";
                    if (node.querySelector("img.platform-icon[src*='facebook']")) return "Facebook";
                    return "Facebook";
                    return "Kick";  // default to Kick if none of the above
                }

                function processNode(node) {
                    try {
                        if (!node || node.nodeType !== 1 || !node.dataset || !node.dataset.from) return;
                        const user = node.dataset.from;
                        const msgNode = node.querySelector('.message');
                        const msg = extractMessage(msgNode);
                        const platform = detectPlatform(node);
                        if (msg) window.onNewMessage({user, message: msg, platform});
                    } catch (e) {}
                }

                const log = document.querySelector('#log');
                if (!log) { console.log('#log not found'); return; }

                log.querySelectorAll('div[data-from]').forEach(processNode);

                const observer = new MutationObserver(muts => {
                    for (const m of muts) for (const n of m.addedNodes) processNode(n);
                });
                observer.observe(log, { childList: true });
                console.log('✅ Chat observer attached (with emote fallback)');
            })();
            """
        )

        await asyncio.Future()


# ---------- main ----------
async def main():
    worker = asyncio.create_task(ntfy_worker())
    try:
        await run_browser()
    finally:
        worker.cancel()


if __name__ == "__main__":
    asyncio.run(main())
