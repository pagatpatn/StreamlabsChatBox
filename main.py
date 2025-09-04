import time
import requests
from playwright.sync_api import sync_playwright
import os

# Environment variables
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
WIDGET_URL = os.environ.get("WIDGET_URL")

if not NTFY_TOPIC or not WIDGET_URL:
    print("Error: NTFY_TOPIC or WIDGET_URL not set.")
    exit(1)

seen_messages = set()

with sync_playwright() as p:
    print("⏳ Launching browser...")
    browser = p.chromium.launch(headless=True, args=[
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu"
    ])
    page = browser.new_page()
    page.goto(WIDGET_URL)
    print("✅ Widget page loaded")

    while True:
        try:
            # Grab all chat messages
            messages = page.eval_on_selector_all(
                ".sl-chat-message",
                "elements => elements.map(e => e.textContent)"
            )

            for msg in messages:
                if msg not in seen_messages:
                    seen_messages.add(msg)
                    # Send to ntfy
                    try:
                        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg)
                        print("💬 Sent to ntfy:", msg)
                    except Exception as e:
                        print("❌ Error sending to ntfy:", e)

            time.sleep(1)
        except Exception as e:
            print("❌ Error scraping messages:", e)
            time.sleep(3)
