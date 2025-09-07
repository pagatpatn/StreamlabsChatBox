import os
import asyncio
import requests
import math
from playwright.async_api import async_playwright

# =====================================================
# --- Config (use Railway ENV vars for security) ---
# =====================================================
CHAT_URL = os.getenv("CHAT_URL")  # must be set in Railway
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh/streamchats123")
DEDUP_CACHE_SIZE = 20  # keep last 20 messages for spam filtering
MAX_LEN = 123  # max chars per ntfy message
SEND_DELAY = 5  # seconds between each message to ntfy

recent_msgs = []


async def send_to_ntfy(user, message, platform="Chat"):
    """Send message(s) to ntfy with dedup + splitting + delay"""
    global recent_msgs
    key = f"{user}:{message}"

    if key in recent_msgs:
        return

    recent_msgs.append(key)
    if len(recent_msgs) > DEDUP_CACHE_SIZE:
        recent_msgs.pop(0)

    # Split long messages
    if len(message) <= MAX_LEN:
        chunks = [message]
    else:
        chunks = [message[i:i+MAX_LEN] for i in range(0, len(message), MAX_LEN)]

    total_parts = len(chunks)

    for i, chunk in enumerate(chunks, start=1):
        suffix = f" [{i}/{total_parts}]" if total_parts > 1 else ""
        try:
            requests.post(
                NTFY_URL,
                data=(chunk + suffix).encode("utf-8"),
                headers={"Title": f"[{platform}] {user}"}
            )
            print(f"✅ Sent to ntfy: [{platform}] {user}: {chunk}{suffix}")
        except Exception as e:
            print(f"❌ Failed to send to ntfy: {e}")

        # Wait SEND_DELAY seconds between all messages (split or not)
        await asyncio.sleep(SEND_DELAY)


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,  # must be True for Railway
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-software-rasterizer"
            ]
        )
        page = await browser.new_page()
        await page.goto(CHAT_URL)

        print("📡 Capturing chat messages from #log...")

        async def on_message(_, data):
            user = data.get("user", "Unknown")
            message = data.get("message", "")
            platform = data.get("platform", "Chat")
            if message.strip():
                await send_to_ntfy(user, message, platform)

        await page.expose_binding("onNewMessage", on_message)

        # JS observer: capture messages + fallback emote handling
        await page.evaluate(r"""
            const log = document.querySelector('#log');
            if (log) {
                function extractMessage(node) {
                    let parts = [];
                    node.querySelectorAll('.message *').forEach(el => {
                        if (el.tagName === "IMG" && el.classList.contains("emote")) {
                            // Try fallback text from alt or filename
                            let alt = el.getAttribute("alt") || "";
                            if (!alt) {
                                let src = el.getAttribute("src") || "";
                                let match = src.match(/\/([^\/]+)\.[a-z]+$/i);
                                alt = match ? match[1] : "emote";
                            }
                            parts.push(`:${alt.toUpperCase()}:`);
                        } else {
                            parts.push(el.textContent);
                        }
                    });
                    // If no nested children, fallback to textContent
                    if (parts.length === 0) {
                        parts.push(node.querySelector('.message')?.innerText.trim() || "");
                    }
                    return parts.join(" ").trim();
                }

                // Capture existing messages
                log.querySelectorAll('div[data-from]').forEach(node => {
                    const user = node.dataset.from;
                    const msg = extractMessage(node);
                    let platform = "Facebook"; // default
                    if (node.querySelector("img.platform-icon[src*='kick']")) platform = "Kick";
                    if (node.querySelector("img.platform-icon[src*='youtube']")) platform = "YouTube";
                    if (node.querySelector("img.platform-icon[src*='twitch']")) platform = "Twitch";
                    if (msg) window.onNewMessage({user, message: msg, platform});
                });

                // Observe new messages
                const observer = new MutationObserver(muts => {
                    for (const m of muts) {
                        for (const node of m.addedNodes) {
                            if (node.nodeType === 1 && node.dataset.from) {
                                const user = node.dataset.from;
                                const msg = extractMessage(node);
                                let platform = "Facebook"; // default
                                if (node.querySelector("img.platform-icon[src*='kick']")) platform = "Kick";
                                if (node.querySelector("img.platform-icon[src*='youtube']")) platform = "YouTube";
                                if (node.querySelector("img.platform-icon[src*='twitch']")) platform = "Twitch";
                                if (msg) window.onNewMessage({user, message: msg, platform});
                            }
                        }
                    }
                });
                observer.observe(log, { childList: true });
                console.log("✅ Chat observer attached to #log");
            } else {
                console.log("❌ #log not found");
            }
        """)

        await asyncio.Future()  # keep alive


async def main():
    if not CHAT_URL:
        raise RuntimeError("CHAT_URL environment variable is required")
    await run()


if __name__ == "__main__":
    asyncio.run(main())
