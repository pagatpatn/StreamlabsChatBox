import os
import time
import requests

# Environment variables
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
WIDGET_TOKEN = os.environ.get("WIDGET_TOKEN")  # Use the token from the hidden input

if not NTFY_TOPIC or not WIDGET_TOKEN:
    print("Error: NTFY_TOPIC or WIDGET_TOKEN not set.")
    exit(1)

# Streamlabs iframe JSON URL
CHAT_URL = f"https://streamlabs.com/widgets/frame/chatbox/custom?type=desktop&token={WIDGET_TOKEN}&format=json"

seen_messages = set()

print("⏳ Starting chat poller...")

while True:
    try:
        resp = requests.get(CHAT_URL, timeout=5)
        if resp.status_code != 200:
            print("❌ Failed to fetch chat:", resp.status_code)
            time.sleep(2)
            continue

        data = resp.json()
        messages = data.get("messages", [])

        for msg in messages:
            msg_id = msg.get("messageId")
            content = msg.get("message")
            if msg_id and msg_id not in seen_messages:
                seen_messages.add(msg_id)
                # Send to ntfy
                try:
                    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=content)
                    print("💬 Sent to ntfy:", content)
                except Exception as e:
                    print("❌ Error sending to ntfy:", e)

        time.sleep(1)
    except Exception as e:
        print("❌ Error fetching chat:", e)
        time.sleep(3)
