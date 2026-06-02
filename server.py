"""
Bardak Studio × SealMary — Telegram Publishing Backend
Запуск: python server.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import base64
import io

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["https://bardakstudioart.github.io", "http://localhost:*", "http://127.0.0.1:*"])

# Bot configs
BOTS = {
    "bardak": {
        "token": os.getenv("BARDAK_BOT_TOKEN", "8822476479:AAHb4B2Mu65cvWbaX_uDHuV4SsJMYNqhXrE"),
        "channel": os.getenv("BARDAK_CHANNEL", "-1003347726742"),
        "name": "Bardak Studio"
    },
    "sealmary": {
        "token": os.getenv("SEALMARY_BOT_TOKEN", ""),
        "channel": os.getenv("SEALMARY_CHANNEL", ""),
        "name": "SealMary"
    }
}


def dataurl_to_bytes(data_url: str) -> bytes:
    """Convert base64 data URL to bytes"""
    if "," in data_url:
        data_url = data_url.split(",")[1]
    return base64.b64decode(data_url)


def send_to_telegram(bot_token: str, channel_id: str, text: str, photos: list) -> dict:
    """Send message/photo/album to Telegram channel"""
    api = f"https://api.telegram.org/bot{bot_token}"

    if not photos:
        # Text only
        resp = requests.post(f"{api}/sendMessage", json={
            "chat_id": channel_id,
            "text": text,
            "parse_mode": "HTML"
        })
        return resp.json()

    elif len(photos) == 1:
        # Single photo with caption
        photo_bytes = dataurl_to_bytes(photos[0])
        resp = requests.post(f"{api}/sendPhoto", data={
            "chat_id": channel_id,
            "caption": text,
        }, files={
            "photo": ("photo.jpg", io.BytesIO(photo_bytes), "image/jpeg")
        })
        return resp.json()

    else:
        # Album via sendMediaGroup
        files = {}
        media = []

        for i, photo_data in enumerate(photos[:10]):
            photo_bytes = dataurl_to_bytes(photo_data)
            field = f"photo{i}"
            files[field] = (f"{field}.jpg", io.BytesIO(photo_bytes), "image/jpeg")
            entry = {"type": "photo", "media": f"attach://{field}"}
            if i == 0:
                entry["caption"] = text
                entry["parse_mode"] = "HTML"
            media.append(entry)

        import json
        resp = requests.post(f"{api}/sendMediaGroup", data={
            "chat_id": channel_id,
            "media": json.dumps(media)
        }, files=files)
        return resp.json()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bots": list(BOTS.keys())})


@app.route("/publish", methods=["POST"])
def publish():
    data = request.json
    bot_key = data.get("bot")          # "bardak" or "sealmary" or "both"
    text = data.get("text", "")
    photos = data.get("photos", [])    # list of base64 data URLs

    if not bot_key:
        return jsonify({"ok": False, "error": "bot is required"}), 400

    results = []

    targets = ["bardak", "sealmary"] if bot_key == "both" else [bot_key]

    for target in targets:
        bot = BOTS.get(target)
        if not bot:
            results.append({"bot": target, "ok": False, "error": "Unknown bot"})
            continue

        if not bot["token"] or not bot["channel"]:
            results.append({"bot": target, "ok": False, "error": f"Bot '{target}' not configured"})
            continue

        try:
            result = send_to_telegram(bot["token"], bot["channel"], text, photos)

            if isinstance(result, list):
                ok = result[0].get("ok", False)
                desc = result[0].get("description", "")
            else:
                ok = result.get("ok", False)
                desc = result.get("description", "")

            results.append({
                "bot": target,
                "name": bot["name"],
                "ok": ok,
                "error": desc if not ok else None
            })

        except Exception as e:
            results.append({"bot": target, "ok": False, "error": str(e)})

    all_ok = all(r["ok"] for r in results)
    return jsonify({"ok": all_ok, "results": results})


@app.route("/test", methods=["POST"])
def test_bot():
    data = request.json
    bot_key = data.get("bot", "bardak")
    bot = BOTS.get(bot_key)

    if not bot or not bot["token"] or not bot["channel"]:
        return jsonify({"ok": False, "error": "Bot not configured"}), 400

    api = f"https://api.telegram.org/bot{bot['token']}"
    resp = requests.post(f"{api}/sendMessage", json={
        "chat_id": bot["channel"],
        "text": f"✅ {bot['name']} Bot подключён! Всё работает 🎉"
    })
    return jsonify(resp.json())


if __name__ == "__main__":
    print("🚀 Bardak Studio Backend запущен!")
    print(f"   Bardak bot: {'✅' if BOTS['bardak']['token'] else '❌ не настроен'}")
    print(f"   SealMary bot: {'✅' if BOTS['sealmary']['token'] else '❌ не настроен'}")
    print("   URL: http://localhost:5000")
    


# ===== INSTAGRAM =====
INSTAGRAM = {
    "bardak": {
        "access_token": os.getenv("BARDAK_IG_TOKEN", ""),
        "ig_user_id": os.getenv("BARDAK_IG_USER_ID", ""),
        "name": "Bardak Studio"
    },
    "sealmary": {
        "access_token": os.getenv("SEALMARY_IG_TOKEN", ""),
        "ig_user_id": os.getenv("SEALMARY_IG_USER_ID", ""),
        "name": "SealMary"
    }
}

IG_API = "https://graph.instagram.com/v19.0"


def upload_image_to_imgbb(image_b64: str) -> str:
    """Upload base64 image to imgbb (free) and get public URL for Instagram"""
    api_key = os.getenv("IMGBB_API_KEY", "")
    if not api_key:
        raise Exception("IMGBB_API_KEY not set in .env — needed for Instagram")
    
    if "," in image_b64:
        image_b64 = image_b64.split(",")[1]
    
    resp = requests.post("https://api.imgbb.com/1/upload", data={
        "key": api_key,
        "image": image_b64,
        "expiration": 3600  # 1 hour, enough for Instagram to fetch
    })
    data = resp.json()
    if not data.get("success"):
        raise Exception("imgbb upload failed: " + str(data))
    return data["data"]["url"]


def publish_to_instagram(ig_config: dict, text: str, photos: list) -> dict:
    """Publish to Instagram via Graph API"""
    token = ig_config["access_token"]
    user_id = ig_config["ig_user_id"]
    
    if not token or not user_id:
        return {"ok": False, "error": "Instagram not configured"}
    
    # Instagram requires public URLs, not base64
    # Upload photos to imgbb first
    photo_urls = []
    for p in photos[:10]:
        url = upload_image_to_imgbb(p)
        photo_urls.append(url)
    
    if not photo_urls:
        return {"ok": False, "error": "No photos to publish"}
    
    if len(photo_urls) == 1:
        # Single image post
        # Step 1: Create media container
        resp = requests.post(f"{IG_API}/{user_id}/media", params={
            "image_url": photo_urls[0],
            "caption": text,
            "access_token": token
        })
        data = resp.json()
        if "id" not in data:
            return {"ok": False, "error": str(data)}
        
        container_id = data["id"]
        
        # Step 2: Publish
        resp2 = requests.post(f"{IG_API}/{user_id}/media_publish", params={
            "creation_id": container_id,
            "access_token": token
        })
        data2 = resp2.json()
        return {"ok": "id" in data2, "post_id": data2.get("id"), "error": str(data2) if "id" not in data2 else None}
    
    else:
        # Carousel post
        # Step 1: Create container for each image
        item_ids = []
        for url in photo_urls:
            resp = requests.post(f"{IG_API}/{user_id}/media", params={
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": token
            })
            data = resp.json()
            if "id" not in data:
                return {"ok": False, "error": "Carousel item failed: " + str(data)}
            item_ids.append(data["id"])
        
        # Step 2: Create carousel container
        resp = requests.post(f"{IG_API}/{user_id}/media", params={
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": text,
            "access_token": token
        })
        data = resp.json()
        if "id" not in data:
            return {"ok": False, "error": "Carousel container failed: " + str(data)}
        
        carousel_id = data["id"]
        
        # Step 3: Publish carousel
        resp2 = requests.post(f"{IG_API}/{user_id}/media_publish", params={
            "creation_id": carousel_id,
            "access_token": token
        })
        data2 = resp2.json()
        return {"ok": "id" in data2, "post_id": data2.get("id"), "error": str(data2) if "id" not in data2 else None}


@app.route("/publish/instagram", methods=["POST"])
def publish_instagram():
    data = request.json or {}
    account_key = data.get("account", "bardak")
    text = data.get("text", "")
    photos = data.get("photos", [])
    # Allow token/user_id override from frontend
    token_override = data.get("token", "")
    user_id_override = data.get("user_id", "")
    
    if not photos:
        return jsonify({"ok": False, "error": "No photos — Instagram requires at least 1 photo"}), 400
    
    results = []
    targets = ["bardak", "sealmary"] if account_key == "both" else [account_key]
    
    for target in targets:
        ig = dict(INSTAGRAM.get(target, {}))
        if not ig:
            results.append({"account": target, "ok": False, "error": "Unknown account"})
            continue
        # Use override tokens if provided
        if token_override and target == account_key:
            ig["access_token"] = token_override
        if user_id_override and target == account_key:
            ig["ig_user_id"] = user_id_override
        try:
            result = publish_to_instagram(ig, text, photos)
            result["account"] = target
            result["name"] = ig.get("name", target)
            results.append(result)
        except Exception as e:
            results.append({"account": target, "ok": False, "error": str(e), "name": ig.get("name", target)})
    
    all_ok = all(r.get("ok") for r in results)
    return jsonify({"ok": all_ok, "results": results})


@app.route("/ig/profile", methods=["POST"])
def ig_profile():
    """Get Instagram user ID from access token"""
    data = request.json or {}
    token = data.get("token", "") or INSTAGRAM["bardak"]["access_token"]
    if not token:
        return jsonify({"ok": False, "error": "token required"}), 400
    
    resp = requests.get(f"https://graph.facebook.com/v19.0/me", params={
        "fields": "id,username",
        "access_token": token
    })
    result = resp.json()
    print(f"IG profile result: {result}")
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("🚀 Bardak Studio Backend запущен!")
    print(f"   Bardak Telegram: {'✅' if BOTS['bardak']['token'] else '❌'}")
    print(f"   SealMary Telegram: {'✅' if BOTS['sealmary']['token'] else '❌'}")
    print(f"   Bardak Instagram: {'✅' if INSTAGRAM['bardak']['access_token'] else '❌'}")
    print(f"   URL: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", debug=False, port=port)
