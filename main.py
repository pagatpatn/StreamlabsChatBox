import os
import time
import requests
import threading
from flask import Flask

app = Flask(__name__)

# Environment variables
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
WIDGET_TOKEN = os.environ.get("WIDGET_TOKEN")

if not NTFY_TOPIC or not WIDGET_TOKEN:
    print("Error: NTFY_TOPIC or WIDGET_TOKEN not set.")
    exit(1)

CHAT_URL = f"https://streamlabs.com/widgets/frame/chatbox/custom?type=desktop&token={WIDGET_TOKEN}&format=json"

seen_messages = set()

def poll_chat():
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
                    try:
                        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=content)
                        print("💬 Sent to ntfy:", content)
                    except Exception as e:
                        print("❌ Error sending to ntfy:", e)
            time.sleep(1)
        except Exception as e:
            print("❌ Error fetching chat:", e)
            time.sleep(3)

# Start polling in a background thread
threading.Thread(target=poll_chat, daemon=True).start()

# Minimal web server to satisfy Railway
@app.route("/")
def home():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"✅ Flask server running on port {port}")
    app.run(host="0.0.0.0", port=port)
