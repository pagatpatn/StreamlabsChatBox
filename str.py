import os
import time
import re
import asyncio
import requests
from datetime import datetime, timedelta, timezone
from kickapi import KickAPI
from playwright.async_api import async_playwright
 
# ================= CONFIG =================
CHAT_URL = "https://streamlabs.com/widgets/chat-box/v1/C6DC1A891DE65F9C4C81C602868ED61C59018D9968330B8B781FA78E095E4A00589BCD3A6BF64B604F9742C6F0B84CCC38884FE4523AC3FFE45812E581444282E462DB432308C0D969F72078093D6B2CFBB49DA03E30676954BB802F25B748ED1208B0E76480F15014408FA3F09FED292ECA427F16820E876BD961E69A"
NTFY_URL = "https://ntfy.sh/streamchats123"
SEND_DELAY = int(os.getenv("MESSAGE_DELAY", 5))
DEDUP_WINDOW = 5
MAX_LEN = 123
KICK_CHANNEL = os.getenv("KICK_CHANNEL", "default_channel")
POLL_INTERVAL = 5
TIME_WINDOW_MINUTES = 0.1

# --- Emoji Mapping ---
EMOJI_MAP = {"GiftedYAY": "🎉", "ErectDance": "💃"}
emoji_pattern = r"\[emote:(\d+):([^\]]+)\]"

def extract_emoji(text: str) -> str:
    matches = re.findall(emoji_pattern, text)
    for emote_id, emote_name in matches:
        text = text.replace(f"[emote:{emote_id}:{emote_name}]", EMOJI_MAP.get(emote_name, f"[{emote_name}]"))
    return text

# --- Kick API Setup ---
kick_api = KickAPI()
if not KICK_CHANNEL:
    raise ValueError("Please set KICK_CHANNEL environment variable")

# ---------- Send Queue & Dedup ----------
recent_msgs = {}
send_queue = asyncio.Queue()

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
    chunks = [message[i:i+MAX_LEN] for i in range(0, len(message), MAX_LEN)] if len(message) > MAX_LEN else [message]
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        suffix = f" [{idx}/{total}]" if total > 1 else ""
        await send_queue.put((platform, user, chunk + suffix))

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

# ---------- Kick API Polling ----------
async def poll_kick_chat():
    channel = kick_api.channel(KICK_CHANNEL)
    if not channel:
        raise ValueError(f"Kick channel '{KICK_CHANNEL}' not found")

    seen_ids = set()
    while True:
        try:
            past_time = datetime.now(timezone.utc) - timedelta(minutes=TIME_WINDOW_MINUTES)
            formatted_time = past_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            chat = kick_api.chat(channel.id, formatted_time)
            messages = []

            if chat and hasattr(chat, "messages") and chat.messages:
                for msg in chat.messages:
                    message_text = extract_emoji(msg.text if hasattr(msg, "text") else "No text")
                    msg_id = msg.id if hasattr(msg, "id") else f"{msg.sender.username}:{message_text}"
                    if msg_id not in seen_ids:
                        seen_ids.add(msg_id)
                        messages.append((msg.sender.username, message_text))
                        print(f"[Kick][{datetime.now().strftime('%H:%M:%S')}] {msg.sender.username}: {message_text}")

            for user, text in messages:
                await enqueue_message("Kick", user, text)

        except Exception as e:
            print(f"❌ Error fetching Kick chat: {e}")

        await asyncio.sleep(POLL_INTERVAL)

# ---------- Browser + DOM observer ----------
async def run_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto(CHAT_URL, wait_until="domcontentloaded")

        try:
            await page.wait_for_selector("#log", timeout=30000)
        except Exception:
            print("❌ #log not found within timeout")

        print("📡 Chat widget loaded — attaching observer...")

        async def on_new_message(_source, payload):
            user = payload.get("user", "Unknown")
            message = payload.get("message", "")
            platform = payload.get("platform", "Facebook")
            if message.strip():
                await enqueue_message(platform, user, message)

        await page.expose_binding("onNewMessage", on_new_message)

        await page.evaluate("""
        (() => {
            function extractMessage(node) {
                if (!node) return '';
                const parts = [];
                node.childNodes.forEach(child => {
                    if (child.nodeType === Node.TEXT_NODE) parts.push(child.textContent);
                    else if (child.nodeType === 1) {
                        if (child.classList.contains('emote')) {
                            const img = child.querySelector('img');
                            parts.push(img?.alt?.trim() || ':EMOTE:');
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
                return "Facebook";
            }
            function processNode(node) {
                if (!node || !node.dataset?.from) return;
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
                for (const m of muts) for (const n of m.addedNodes) processNode(n);
            });
            observer.observe(log, { childList: true });
        })();
        """)

        await asyncio.Future()

# ---------- main ----------
async def main():
    worker = asyncio.create_task(ntfy_worker())
    kick_poll = asyncio.create_task(poll_kick_chat())
    try:
        await run_browser()
    finally:
        worker.cancel()
        kick_poll.cancel()

if __name__ == "__main__":
    asyncio.run(main())
