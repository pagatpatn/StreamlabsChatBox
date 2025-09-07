import asyncio
import requests
import time
import hashlib
from playwright.async_api import async_playwright

# ================= CONFIG =================
CHAT_URL = "https://streamlabs.com/widgets/chat-box/v1/C6DC1A891DE65F9C4C81C602868ED61C59018D9968330B8B781FA78E095E4A00589BCD3A6BF64B604F9742C6F0B84CCC38884FE4523AC3FFE45812E581444282E462DB432308C0D969F72078093D6B2CFBB49DA03E30676954BB802F25B748ED1208B0E76480F15014408FA3F09FED292ECA427F16820E876BD961E69A"
NTFY_URL = "https://ntfy.sh/streamchats123"
SEND_DELAY = 5
DEDUP_WINDOW = 5
MAX_LEN = 123
POLL_INTERVAL = 0.5

recent_msgs = {}      # { hash_key: timestamp }
send_queue = asyncio.Queue()

# ---------- Enqueue ----------
async def enqueue_message(platform: str, user: str, message: str):
    key_hash = hashlib.sha256(f"{platform}:{user}:{message}".encode()).hexdigest()
    now = time.time()
    if key_hash in recent_msgs and now - recent_msgs[key_hash] < DEDUP_WINDOW:
        return
    recent_msgs[key_hash] = now
    # cleanup
    for k in list(recent_msgs.keys()):
        if now - recent_msgs[k] > DEDUP_WINDOW:
            del recent_msgs[k]

    chunks = [message[i:i+MAX_LEN] for i in range(0, len(message), MAX_LEN)] if len(message) > MAX_LEN else [message]
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        suffix = f" [{idx}/{total}]" if total > 1 else ""
        await send_queue.put((platform, user, chunk + suffix))

# ---------- NTFY worker ----------
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

# ---------- Browser ----------
async def run_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto(CHAT_URL, wait_until="domcontentloaded")

        try:
            await page.wait_for_selector("#log", timeout=30000)
        except Exception:
            print("❌ #log not found within timeout")

        print("📡 Chat widget loaded — observer + polling active")

        async def on_new_message(user, message, platform):
            await enqueue_message(platform, user, message)

        await page.expose_binding("onNewMessage", lambda _, payload: on_new_message(
            payload.get("user", "Unknown"),
            payload.get("message", ""),
            payload.get("platform", "Kick")
        ))

        seen_hashes = set()

        await page.evaluate("""
            (() => {
                function extractMessage(node) {
                    if (!node) return '';
                    const parts = [];
                    node.childNodes.forEach(c => {
                        if (c.nodeType === Node.TEXT_NODE) parts.push(c.textContent);
                        else if (c.nodeType === 1 && c.classList.contains('emote')) {
                            const img = c.querySelector('img'); 
                            parts.push(img?.alt?.trim() || ':KEKW:');
                        } else parts.push(c.textContent || '');
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
                const log = document.querySelector('#log');
                if (!log) return;
                const observer = new MutationObserver(muts => {
                    muts.forEach(m => m.addedNodes.forEach(n => {
                        try {
                            if (!n.dataset || !n.dataset.from) return;
                            const user = n.dataset.from;
                            const msgNode = n.querySelector('.message');
                            const msg = extractMessage(msgNode);
                            const platform = detectPlatform(n);
                            if (msg) window.onNewMessage({user, message: msg, platform});
                        } catch(e){}
                    }));
                });
                observer.observe(log, {childList: true});
            })();
        """)

        # --- Polling backup ---
        while True:
            nodes = await page.query_selector_all("div[data-from]")
            for node in nodes:
                user = await node.get_attribute("data-from") or "Unknown"
                msg_node = await node.query_selector(".message") or await node.query_selector(".message-text")
                message = await msg_node.inner_text() if msg_node else ""
                platform = "Kick"
                icons = await node.query_selector_all("img.platform-icon")
                for icon in icons:
                    src = await icon.get_attribute("src") or ""
                    if "youtube" in src: platform = "YouTube"
                    elif "twitch" in src: platform = "Twitch"
                    elif "facebook" in src: platform = "Facebook"

                # generate hash to prevent duplicate sending
                key_hash = hashlib.sha256(f"{platform}:{user}:{message}".encode()).hexdigest()
                if key_hash not in seen_hashes:
                    seen_hashes.add(key_hash)
                    await on_new_message(user, message, platform)

            await asyncio.sleep(POLL_INTERVAL)

# ---------- Main ----------
async def main():
    worker = asyncio.create_task(ntfy_worker())
    try:
        await run_browser()
    finally:
        worker.cancel()

if __name__ == "__main__":
    asyncio.run(main())
