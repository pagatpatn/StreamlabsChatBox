import os
import time
import re
import asyncio
import requests
from datetime import datetime
from playwright.async_api import async_playwright
import json
import websockets
import random

# ================= CONFIG =================
CHAT_URL = os.getenv("CHAT_URL")
NTFY_URL = os.getenv("NTFY_URL")
SEND_DELAY = int(os.getenv("MESSAGE_DELAY", 5))
DEDUP_WINDOW = 5
MAX_LEN = 123
CHATROOM_ID = os.getenv("CHATROOM_ID")
WS_URL = os.getenv("WS_URL")

# --- Emoji Mapping ---
EMOJI_MAP = {"GiftedYAY": "🎉", "ErectDance": "💃"}
emoji_pattern = r"\[emote:(\d+):([^\]]+)\]"

def extract_emoji(text: str) -> str:
    matches = re.findall(emoji_pattern, text)
    for emote_id, emote_name in matches:
        text = text.replace(f"[emote:{emote_id}:{emote_name}]", EMOJI_MAP.get(emote_name, f"[{emote_name}]"))
    return text

# ---------- Send Queue & Dedup ----------
recent_msgs = {}
send_queue = asyncio.Queue()

async def enqueue_message(platform: str, user: str, message: str):
    now = time.time()
    key = f"{platform}:{user}:{message}"
    last_sent = recent_msgs.get(key)
    if last_sent and now - last_sent < DEDUP_WINDOW:
        return
    recent_msgs[key] = now
    for k, t in list(recent_msgs.items()):
        if now - t > DEDUP_WINDOW * 2:
            del recent_msgs[k]

    chunks = [message[i:i+MAX_LEN] for i in range(0, len(message), MAX_LEN)] if len(message) > MAX_LEN else [message]
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        suffix = f" [{idx}/{total}]" if total > 1 else ""
        await send_queue.put((platform, user, chunk + suffix))

# ---------- NTFY worker with FIFO and immediate first message ----------
async def ntfy_worker():
    first_message = True
    while True:
        platform, user, msg = await send_queue.get()

        try:
            await asyncio.to_thread(
                requests.post,
                NTFY_URL,
                data=msg.encode("utf-8"),
                headers={"Title": f"[{platform}] {user}"}
            )
        except Exception as e:
            print(f"❌ Failed to send to ntfy: {e}")

        send_queue.task_done()

        # Delay only if there are more messages waiting
        if not send_queue.empty():
            await asyncio.sleep(SEND_DELAY)
        first_message = False

# ---------- Kick WebSocket ----------
last_message_by_user = {}

def split_message(text, limit=MAX_LEN):
    if len(text) <= limit:
        return [text]
    parts = []
    for i in range(0, len(text), limit):
        parts.append(text[i:i + limit])
    total = len(parts)
    return [f"{part} [{i+1}/{total}]" for i, part in enumerate(parts)]

async def handle_kick_event(event):
    event_type = event.get("event")
    data = json.loads(event.get("data", "{}"))

    if event_type == "App\\Events\\ChatMessageEvent":
        user = data["sender"]["username"]
        text = extract_emoji(data["content"])
        if last_message_by_user.get(user) == text:
            return
        last_message_by_user[user] = text
        parts = split_message(text)
        for part in parts:
            await enqueue_message("Kick", user, part)
        print(f"[💬 {user}] {text}")

    elif event_type == "App\\Events\\SubscriptionEvent":
        user = data["user"]["username"]
        months = data.get("months", 1)
        msg = f"🎉 Subscribed for {months} month(s)!"
        await enqueue_message("Kick", user, msg)
        print(f"[⭐ SUB] {user} → {msg}")

    elif event_type == "App\\Events\\GiftedSubEvent":
        gifter = data["gifter"]["username"]
        amount = data.get("gift_count", 1)
        msg = f"🎁 Gifted {amount} sub(s)!"
        await enqueue_message("Kick", gifter, msg)
        print(f"[🎁 GIFT] {gifter} → {msg}")

    elif event_type == "App\\Events\\TipEvent":
        user = data["sender"]["username"]
        amount = data.get("amount", 0)
        currency = data.get("currency", "USD")
        msg = f"💸 Tipped {amount} {currency}"
        await enqueue_message("Kick", user, msg)
        print(f"[💸 TIP] {user} → {msg}")

    elif event_type == "App\\Events\\RaidEvent":
        user = data["raider"]["username"]
        viewers = data.get("viewer_count", 0)
        msg = f"⚡ Raided with {viewers} viewers!"
        await enqueue_message("Kick", user, msg)
        print(f"[⚡ RAID] {user} → {msg}")

    elif event_type == "App\\Events\\StickerEvent":
        user = data["sender"]["username"]
        sticker = data["sticker"]["name"]
        msg = f"🌟 Sent sticker: {sticker}"
        await enqueue_message("Kick", user, msg)
        print(f"[🌟 STICKER] {user} → {msg}")

async def listen_kick_websocket(chatroom_id):
    async for ws in websockets.connect(WS_URL, ping_interval=20, ping_timeout=20):
        try:
            print("✅ Connected to Kick chat WebSocket")
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("event") == "pusher:connection_established":
                subscribe_payload = {
                    "event": "pusher:subscribe",
                    "data": {
                        "auth": "",
                        "channel": f"chatrooms.{chatroom_id}.v2",
                    },
                }
                await ws.send(json.dumps(subscribe_payload))
                print(f"📡 Subscribed to chatroom {chatroom_id}")
            async for message in ws:
                try:
                    event = json.loads(message)
                    await handle_kick_event(event)
                except Exception:
                    pass
        except Exception:
            print("❌ Kick WS connection error, retrying...")
        finally:
            await asyncio.sleep(5)

# ---------- Browser + DOM observer (Streamlabs) ----------
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
    ntfy_worker_task = asyncio.create_task(ntfy_worker())
    kick_ws_task = asyncio.create_task(listen_kick_websocket(CHATROOM_ID))
    try:
        await run_browser()
    finally:
        ntfy_worker_task.cancel()
        kick_ws_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
