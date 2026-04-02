from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def get_user(nickname):
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/line_users?nickname=eq.{nickname}&select=user_id",
        headers=supabase_headers()
    )
    data = res.json()
    return data[0]["user_id"] if data else None

def get_user_by_id(user_id):
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/line_users?user_id=eq.{user_id}&select=nickname",
        headers=supabase_headers()
    )
    data = res.json()
    return data[0]["nickname"] if data else None

def save_user(nickname, user_id):
    requests.post(
        f"{SUPABASE_URL}/rest/v1/line_users",
        headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
        json={"nickname": nickname, "user_id": user_id}
    )

def delete_pending(user_id):
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/line_users?user_id=eq.{user_id}&nickname=eq.PENDING_{user_id}",
        headers=supabase_headers()
    )

def is_pending(user_id):
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/line_users?user_id=eq.{user_id}&nickname=like.PENDING_*&select=nickname",
        headers=supabase_headers()
    )
    return len(res.json()) > 0

def set_pending(user_id):
    requests.post(
        f"{SUPABASE_URL}/rest/v1/line_users",
        headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates"},
        json={"nickname": f"PENDING_{user_id}", "user_id": user_id}
    )

def reply_message(reply_token, text):
    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={"Authorization": f"Bearer {LINE_CHANNEL_TOKEN}", "Content-Type": "application/json"},
        json={"replyToken": reply_token, "messages": [{"type": "text", "text": text}]}
    )

def push_message(user_id, text):
    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {LINE_CHANNEL_TOKEN}", "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{"type": "text", "text": text}]}
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.json
    for event in body.get("events", []):
        user_id = event["source"]["userId"]
        reply_token = event.get("replyToken", "")

        if event["type"] == "follow":
            set_pending(user_id)
            reply_message(reply_token,
                "🏠 歡迎使用智慧房價診斷系統！\n\n請輸入你想要的暱稱來完成綁定👇\n（暱稱不可重複）")

        elif event["type"] == "message" and event["message"]["type"] == "text":
            text = event["message"]["text"].strip()

            if is_pending(user_id):
                if get_user(text):
                    reply_message(reply_token, f"❌ 暱稱「{text}」已被使用，請換一個！")
                else:
                    delete_pending(user_id)
                    save_user(text, user_id)
                    reply_message(reply_token,
                        f"✅ 綁定成功！\n你的暱稱是：{text}\n\n請到網站輸入此暱稱即可接收專屬推播！\nhttps://house-diagnosis.streamlit.app/")
            else:
                reply_message(reply_token,
                    "💡 請到網站輸入你的暱稱來接收房價推播通知！\nhttps://house-diagnosis.streamlit.app/")

    return jsonify({"status": "ok"})

@app.route("/push", methods=["POST"])
def push():
    data = request.json
    nickname = data.get("nickname", "")
    message = data.get("message", "")
    user_id = get_user(nickname)
    if not user_id:
        return jsonify({"status": "error", "message": "找不到此暱稱"}), 404
    push_message(user_id, message)
    return jsonify({"status": "ok", "sent_to": nickname})

@app.route("/check/<nickname>", methods=["GET"])
def check(nickname):
    user_id = get_user(nickname)
    return jsonify({"exists": user_id is not None})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)