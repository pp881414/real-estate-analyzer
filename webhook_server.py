from flask import Flask, request, jsonify
import json
import os
import requests

app = Flask(__name__)

# 儲存用戶 ID 的檔案
USERS_FILE = "line_users.json"
LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

# LINE Webhook 接收端
@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.json
    for event in body.get("events", []):
        # 用戶加入或傳訊息時，儲存他的 User ID
        if event["type"] in ("follow", "message"):
            user_id = event["source"]["userId"]
            users = load_users()
            if user_id not in users:
                users.append(user_id)
                save_users(users)
                # 發送歡迎訊息
                send_message(user_id, "🏠 歡迎加入房價追蹤！\n請至網站按「推播給我」，即可收到 CP 值物件通知！")
    return jsonify({"status": "ok"})

# Streamlit 呼叫這個端點來推播給所有用戶
@app.route("/broadcast", methods=["POST"])
def broadcast():
    data = request.json
    message = data.get("message", "")
    users = load_users()
    for user_id in users:
        send_message(user_id, message)
    return jsonify({"status": "ok", "sent": len(users)})

# 取得用戶數量
@app.route("/users/count", methods=["GET"])
def user_count():
    users = load_users()
    return jsonify({"count": len(users)})

def send_message(user_id, message):
    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": message}]
        }
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)