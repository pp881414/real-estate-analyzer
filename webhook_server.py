from flask import Flask, request, jsonify
import json
import os
import requests

app = Flask(__name__)

USERS_FILE = "line_users.json"
LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")

# 等待用戶輸入暱稱的狀態
PENDING_FILE = "pending_users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False)

def load_pending():
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_pending(pending):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False)

def reply_message(reply_token, text):
    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": text}]
        }
    )

def push_message(user_id, text):
    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "to": user_id,
            "messages": [{"type": "text", "text": text}]
        }
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.json
    for event in body.get("events", []):
        user_id = event["source"]["userId"]
        reply_token = event.get("replyToken", "")

        # 用戶加好友
        if event["type"] == "follow":
            pending = load_pending()
            pending[user_id] = True
            save_pending(pending)
            reply_message(reply_token,
                "🏠 歡迎使用智慧房價診斷系統！\n\n請輸入你想要的暱稱來完成綁定👇\n（暱稱不可重複）")

        # 用戶傳訊息
        elif event["type"] == "message" and event["message"]["type"] == "text":
            text = event["message"]["text"].strip()
            pending = load_pending()

            if user_id in pending:
                # 用戶正在設定暱稱
                users = load_users()

                # 檢查暱稱是否重複
                if text in users:
                    reply_message(reply_token,
                        f"❌ 暱稱「{text}」已被使用，請換一個！")
                else:
                    # 綁定成功
                    users[text] = user_id
                    save_users(users)
                    del pending[user_id]
                    save_pending(pending)
                    reply_message(reply_token,
                        f"✅ 綁定成功！\n你的暱稱是：{text}\n\n請到網站輸入此暱稱即可接收專屬推播！\nhttps://house-diagnosis.streamlit.app/")
            else:
                reply_message(reply_token,
                    "💡 請到網站輸入你的暱稱來接收房價推播通知！\nhttps://house-diagnosis.streamlit.app/")

    return jsonify({"status": "ok"})

# Streamlit 呼叫：推播給指定暱稱的用戶
@app.route("/push", methods=["POST"])
def push():
    data = request.json
    nickname = data.get("nickname", "")
    message = data.get("message", "")
    users = load_users()

    if nickname not in users:
        return jsonify({"status": "error", "message": "找不到此暱稱"}), 404

    user_id = users[nickname]
    push_message(user_id, message)
    return jsonify({"status": "ok", "sent_to": nickname})

# 查詢暱稱是否已綁定
@app.route("/check/<nickname>", methods=["GET"])
def check(nickname):
    users = load_users()
    return jsonify({"exists": nickname in users})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)