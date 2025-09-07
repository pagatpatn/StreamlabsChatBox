import asyncio
import requests
import time
from playwright.async_api import async_playwright

# ================= CONFIG =================
CHAT_URL = "https://streamlabs.com/widgets/chat-box/v1/C6DC1A891DE65F9C4C81C602868ED61C59018D9968330B8B781FA78E095E4A00589BCD3A6BF64B604F9742C6F0B84CCC38884FE4523AC3FFE45812E581444282E462DB432308C0D969F72078093D6B2CFBB49DA03E30676954BB802F25B748ED1208B0E76480F15014408FA3F09FED292ECA427F16820E876BD961E69A"
NTFY_URL = "https://ntfy.sh/streamchats123"
SEND_DELAY = 5
DEDUP_WINDOW = 5
MAX_LEN = 123
POLL_INTERVAL = 0.5  # seconds

recent_msgs = {}        
send_queue = asyncio.Queue()

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
            print("❌ #log not found within timeout; widget might not have loaded.")

        print("📡 Chat widget loaded — starting polling...")

        async def on_new_message(user, message, platform):
            if message and message.strip():
                await enqueue_message(platform, user, message)

        await page.expose_binding("onNewMessage", lambda _, payload: on_new_message(
            payload.get("user", "Unknown"),
            payload.get("message", ""),
            payload.get("platform", "Kick")
        ))

        seen_nodes = set()

        while True:
            nodes = await page.query_selector_all("div[data-from]")
            for node in nodes:
                node_id = await node.get_attribute("data-id") or str(id(node))
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)

                user = await node.get_attribute("data-from") or "Unknown"
                msg_node = await node.query_selector(".message") or await node.query_selector(".message-text")
                if msg_node:
                    message = await msg_node.inner_text()
                    platform = "Kick"
                    icons = await node.query_selector_all("img.platform-icon")
                    for icon in icons:
                        src = await icon.get_attribute("src") or ""
                        if "youtube" in src: platform = "YouTube"
                        elif "twitch" in src: platform = "Twitch"
                        elif "facebook" in src: platform = "Facebook"

                    await on_new_message(user, message, platform)

            await asyncio.sleep(POLL_INTERVAL)

async def main():
    worker = asyncio.create_task(ntfy_worker())
    try:
        await run_browser()
    finally:
        worker.cancel()

if __name__ == "__main__":
    asyncio.run(main())
