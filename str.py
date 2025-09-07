import os
import asyncio
import requests
from playwright.async_api import async_playwright

# ==============================
# Config
# ==============================
NTFY_URL = os.getenv("NTFY_URL")
KICK_CHAT_URL = os.getenv("KICK_CHAT_URL")       # Kick chat embed
YOUTUBE_CHAT_URL = os.getenv("YOUTUBE_CHAT_URL") # YouTube live chat embed
FB_WIDGET_URL = os.getenv("FB_WIDGET_URL")       # Streamlabs/Facebook widget

# Track seen messages to avoid duplicates
seen_messages = set()

# ==============================
# Helpers
# ==============================
async def send_to_ntfy(message: str):
    """Send chat message to ntfy with 5s delay."""
    if not NTFY_URL:
        print("❌ NTFY_URL not set")
        return
    try:
        requests.post(NTFY_URL, data=message.encode("utf-8"))
        print(f"✅ Sent to ntfy: {message}")
    except Exception as e:
        print(f"❌ Failed to send message: {e}")
    await asyncio.sleep(5)

def format_kick(username: str, parts):
    """Convert Kick message parts into string with emote fallback."""
    final = []
    for p in parts:
        if isinstance(p, str):
            final.append(p)
        else:
            alt = p.get("alt") or "EMOTE"
            final.append(f":{alt.strip(':')}:")
    return f"[Kick] {username}: {''.join(final)}"

def format_youtube(username: str, text: str):
    return f"[YouTube] {username}: {text}"

def format_facebook(username: str, text: str):
    return f"[Facebook] {username}: {text}"

# ==============================
# Scrapers
# ==============================
async def scrape_kick(page):
    messages = await page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('[data-chat-entry]').forEach(el => {
            const userEl = el.querySelector('[data-chat-entry-username]');
            const msgEl = el.querySelector('[data-chat-entry-message]');
            if (!userEl || !msgEl) return;

            const username = userEl.textContent.trim();
            const parts = [];
            msgEl.childNodes.forEach(node => {
                if (node.nodeType === Node.TEXT_NODE) {
                    parts.push(node.textContent);
                } else if (node.nodeType === Node.ELEMENT_NODE) {
                    if (node.tagName === "IMG" && node.alt) {
                        parts.push({alt: node.alt});
                    } else {
                        parts.push(node.textContent);
                    }
                }
            });

            items.push({
                id: el.getAttribute("data-id"),
                username,
                parts
            });
        });
        return items;
    }""")

    results = []
    for msg in messages:
        if msg["id"] in seen_messages:
            continue
        seen_messages.add(msg["id"])
        results.append(format_kick(msg["username"], msg["parts"]))
    return results

async def scrape_youtube(page):
    messages = await page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('#items #message').forEach(el => {
            const userEl = el.closest('#content').querySelector('#author-name');
            if (!userEl) return;
            items.push({
                id: el.closest('yt-live-chat-text-message-renderer').getAttribute('id'),
                username: userEl.textContent.trim(),
                text: el.textContent.trim()
            });
        });
        return items;
    }""")

    results = []
    for msg in messages:
        if msg["id"] in seen_messages:
            continue
        seen_messages.add(msg["id"])
        results.append(format_youtube(msg["username"], msg["text"]))
    return results

async def scrape_facebook(page):
    messages = await page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('div[data-from]').forEach(el => {
            const nameEl = el.querySelector('.name');
            const msgEl = el.querySelector('.message');
            if (!nameEl || !msgEl) return;

            items.push({
                id: el.getAttribute("data-id"),
                username: nameEl.textContent.trim(),
                text: msgEl.textContent.trim()
            });
        });
        return items;
    }""")

    results = []
    for msg in messages:
        if msg["id"] in seen_messages:
            continue
        seen_messages.add(msg["id"])
        results.append(format_facebook(msg["username"], msg["text"]))
    return results

# ==============================
# Main Runner
# ==============================
async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])

        pages = {}
        if KICK_CHAT_URL:
            pages["kick"] = await browser.new_page()
            await pages["kick"].goto(KICK_CHAT_URL, wait_until="domcontentloaded")
            print("✅ Connected to Kick chat")
        if YOUTUBE_CHAT_URL:
            pages["yt"] = await browser.new_page()
            await pages["yt"].goto(YOUTUBE_CHAT_URL, wait_until="domcontentloaded")
            print("✅ Connected to YouTube chat")
        if FB_WIDGET_URL:
            pages["fb"] = await browser.new_page()
            await pages["fb"].goto(FB_WIDGET_URL, wait_until="domcontentloaded")
            print("✅ Connected to Facebook widget")

        while True:
            if "kick" in pages:
                msgs = await scrape_kick(pages["kick"])
                for m in msgs:
                    await send_to_ntfy(m)

            if "yt" in pages:
                msgs = await scrape_youtube(pages["yt"])
                for m in msgs:
                    await send_to_ntfy(m)

            if "fb" in pages:
                msgs = await scrape_facebook(pages["fb"])
                for m in msgs:
                    await send_to_ntfy(m)

            await asyncio.sleep(1)

async def main():
    await run()

if __name__ == "__main__":
    asyncio.run(main())
