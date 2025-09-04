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
                sender = msg.get("from")  # the user who sent the message
                content = msg.get("message")
                if msg_id and msg_id not in seen_messages:
                    seen_messages.add(msg_id)
                    # Log to console immediately
                    print(f"💬 New message from {sender}: {content}")
                    # Send to ntfy
                    try:
                        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=content)
                    except Exception as e:
                        print("❌ Error sending to ntfy:", e)
            time.sleep(1)
        except Exception as e:
            print("❌ Error fetching chat:", e)
            time.sleep(3)
