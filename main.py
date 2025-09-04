# main.py
import os
import time
import requests
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
WIDGET_TOKEN = os.environ.get("WIDGET_TOKEN")
CHAT_URL = f"https://streamlabs.com/widgets/frame/chatbox/custom?type=desktop&token={WIDGET_TOKEN}&format=json"

seen_messages = set()

# Simple HTTP server to satisfy Railway
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("", port), DummyHandler)
    print(f"✅ Dummy server running on port {port}")
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

# Polling chat messages
print("⏳ Starting chat poller...")
while True:
    try:
        resp = requests.get(CHAT_URL, timeout=5)
        if resp.status_code != 200:
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
