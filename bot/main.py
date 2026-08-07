"""
💰 Finance Bot + Mini App
"""

import os, re, json, hmac, hashlib, urllib.parse
from dotenv import load_dotenv

# 🔐 Загружаем .env ПЕРЕД всем остальным
load_dotenv("/home/runner/workspace/.env")

import telebot
from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from db import (
    init_db,
    add_transaction,
    get_balance,
    get_history,
    get_categories_summary,
    delete_last,
    get_monthly_summary,
    save_user,
    set_reminder,
    get_reminder,
    get_all_reminder_users,
)

# 🔑 Настройки
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("⚠️ TELEGRAM_BOT_TOKEN не найден в .env!")

REPLIT_DOMAINS = os.environ.get("REPLIT_DOMAINS", "")
PRIMARY_DOMAIN = REPLIT_DOMAINS.split(",")[0] if REPLIT_DOMAINS else ""
MINIAPP_URL = f"https://{PRIMARY_DOMAIN}/miniapp/" if PRIMARY_DOMAIN else ""

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
app = Flask(__name__)

# 📥 Регистрируем обработчик выписок ПЕРВЫМ, до всех остальных обработчиков
import importer
importer.register(bot)


# 🔐 Валидация initData
def verify_telegram_init_data(init_data: str, bot_token: str) -> int | None:
    if not init_data:
        return None
    try:
        parsed = urllib.parse.parse_qs(init_data)
        hash_val = parsed.pop("hash", [None])[0]
        data_check_string = "\n".join(f"{k}={v[0]}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, hash_val):
            return None
        return json.loads(parsed.get("user", ["{}"])[0]).get("id")
    except:
        return None


# 🌐 API
@app.route("/api/transaction", methods=["POST"])
def api_add_transaction():
    data = request.get_json() or {}
    init_data = request.headers.get("X-Telegram-InitData", "")
    uid = verify_telegram_init_data(init_data, TOKEN)
    if not uid:
        return jsonify({"error": "Invalid auth"}), 401
    try:
        add_transaction(
            uid,
            data["type"],
            float(data["amount"]),
            data.get("category", "Без категории"),
            "",
        )
        try:
            icon = (
                "📈"
                if data["type"] == "income"
                else ("🏦" if data["type"] == "saving" else "📉")
            )
            bot.send_message(uid, f"{icon} {data['type']}: {data['amount']}₽")
        except:
            pass
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/balance", methods=["GET"])
def api_get_balance():
    init_data = request.args.get(
        "initData", request.headers.get("X-Telegram-InitData", "")
    )
    uid = verify_telegram_init_data(init_data, TOKEN)
    if not uid:
        return jsonify({"error": "Invalid auth"}), 401
    bal = get_balance(uid)
    m = get_monthly_summary(uid)
    return jsonify(
        {
            "balance": bal,
            "income": m["income"] if m else 0,
            "expense": m["expense"] if m else 0,
        }
    ), 200


@app.route("/api/history", methods=["GET"])
def api_get_history():
    init_data = request.args.get(
        "initData", request.headers.get("X-Telegram-InitData", "")
    )
    uid = verify_telegram_init_data(init_data, TOKEN)
    if not uid:
        return jsonify({"error": "Invalid auth"}), 401
    rows = get_history(uid, int(request.args.get("limit", 10)))
    return jsonify(
        [
            {
                "id": r["id"],
                "type": r["type"],
                "amount": r["amount"],
                "category": r["category"],
                "date": r["created_at"],
            }
            for r in rows
        ]
    ), 200


# 📱 Mini App
@app.route("/miniapp/", methods=["GET"])
@app.route("/miniapp/index.html", methods=["GET"])
def serve_miniapp():
    p = os.path.join(os.path.dirname(__file__), "miniapp.html")
    with open(p, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}

# 🤖 Bot
HELP = """
💰 *Бот учёта финансов*

*Добавить транзакцию:*
`/add доход 5000 Зарплата`
`/add расход 350 Еда`
`/add saving 1000 Копилка`

*Просмотр данных:*
/balance — текущий баланс
/history — последние 
