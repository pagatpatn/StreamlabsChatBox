import os
import threading
import requests
from flask import Flask
import socketio

app = Flask(__name__)

# Environment variables
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
WIDGET_TOKEN = os.environ.get("WIDGET_TOKEN")

if not NTFY_TOPIC or not WIDGET_TOKEN:
    print("❌ NTFY_TOPIC or WIDGET_TOKEN not set")
    exit(1)

# Socket.IO client
sio = socketio.Client(logger=True, engineio_logger=False)

@sio.event
def connect():
    print("✅ Connected to Streamlabs Socket.IO")

@sio.event
def disconnect():
    print("❌ Disconnected from Streamlabs")

@sio.on('message')
def on_message(data):
    try:
        msg = data.get('message')
        sender = data.get('from')
        if msg:
            print(f"💬 {sender}: {msg}")
            # Send to ntfy
            try:
                requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg)
            except Exception as e:
                print("❌ Error sending to ntfy:", e)
    except Exception as e:
        print("❌ Error processing message:", e)

def start_socketio():
    sio.connect(f"https://sockets.streamlabs.com?token={WIDGET_TOKEN}")
    sio.wait()

# Start Socket.IO in background thread
threading.Thread(target=start_socketio, daemon=True).start()

# Minimal Flask server to satisfy Railway
@app.route("/")
def home():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"✅ Flask server running on port {port}")
    app.run(host="0.0.0.0", port=port)
