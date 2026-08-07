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
/history — последние 10 операций
/month — сводка за текущий месяц
/categories — расходы по категориям
/stats — диаграмма расходов за 7 дней 📊

*Напоминания:*
/remind 21:00 — напоминание каждый день в 21:00
/remind off — отключить напоминание

*Управление:*
/undo — удалить последнюю запись
/help — эта справка
"""


def kb():
    k = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.add(
        KeyboardButton("💳 Баланс"),
        KeyboardButton("📋 История"),
        KeyboardButton("📊 Категории"),
    )
    if MINIAPP_URL:
        k.add(KeyboardButton("📱 Приложение", web_app=WebAppInfo(url=MINIAPP_URL)))
    return k


def inline_kb(uid=None):
    if not MINIAPP_URL:
        return None
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("📱 Mini App", web_app=WebAppInfo(url=MINIAPP_URL))
    )


@bot.message_handler(commands=["start"])
def start(m):
    save_user(m.from_user.id, m.chat.id)
    bot.send_message(
        m.chat.id,
        f"Привет, {m.from_user.first_name}! 👋\n{HELP}",
        parse_mode="Markdown",
        reply_markup=kb(),
    )
    if MINIAPP_URL:
        bot.send_message(
            m.chat.id, "Открыть приложение:", reply_markup=inline_kb(m.from_user.id)
        )


@bot.message_handler(commands=["help"])
def help_cmd(m):
    bot.send_message(m.chat.id, HELP, parse_mode="Markdown", reply_markup=kb())


@bot.message_handler(commands=["remind"])
def remind(m):
    save_user(m.from_user.id, m.chat.id)
    p = m.text.split(maxsplit=1)
    arg = p[1].strip() if len(p) > 1 else ""
    if arg.lower() == "off":
        set_reminder(m.from_user.id, None, None)
        return bot.send_message(
            m.chat.id, "🔕 Напоминания выключены", reply_markup=kb()
        )
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", arg)
    if not match:
        return bot.send_message(
            m.chat.id, "❌ Формат: /remind 21:00", reply_markup=kb()
        )
    h, mn = int(match.group(1)), int(match.group(2))
    if not (0 <= h <= 23 and 0 <= mn <= 59):
        return bot.send_message(m.chat.id, "❌ Некорректное время", reply_markup=kb())
    set_reminder(m.from_user.id, h, mn)
    bot.send_message(
        m.chat.id, f"✅ Напоминание на {h:02d}:{mn:02d}", reply_markup=kb()
    )


@bot.message_handler(commands=["add"])
def add(m):
    save_user(m.from_user.id, m.chat.id)
    p = m.text.split(maxsplit=3)
    if len(p) < 4:
        return bot.send_message(
            m.chat.id, "❌ Формат: /add тип сумма категория", reply_markup=kb()
        )
    _, t, a, c = p
    tmap = {
        "доход": "income",
        "income": "income",
        "расход": "expense",
        "expense": "expense",
        "накопления": "saving",
        "saving": "saving",
    }
    t = tmap.get(t.lower())
    if not t:
        return bot.send_message(
            m.chat.id, "❌ Тип: доход, расход или saving", reply_markup=kb()
        )
    try:
        a = float(a.replace(",", "."))
    except:
        return bot.send_message(m.chat.id, "❌ Сумма числом", reply_markup=kb())
    add_transaction(m.from_user.id, t, a, c, "")
    bot.send_message(
        m.chat.id,
        f"✅ {t}: {a}₽ ({c})\nБаланс: {get_balance(m.from_user.id)}₽",
        reply_markup=kb(),
    )


@bot.message_handler(commands=["balance"])
@bot.message_handler(func=lambda m: m.text == "💳 Баланс")
def balance(m):
    b = get_balance(m.from_user.id)
    mo = get_monthly_summary(m.from_user.id)
    inc = mo["income"] if mo else 0
    exp = mo["expense"] if mo else 0
    bot.send_message(
        m.chat.id,
        f"{'🟢' if b >= 0 else '🔴'} Баланс: {b}₽\n📅 Месяц: +{inc} / -{exp}",
        reply_markup=kb(),
    )


@bot.message_handler(commands=["history"])
@bot.message_handler(func=lambda m: m.text == "📋 История")
def history(m):
    rows = get_history(m.from_user.id, 10)
    if not rows:
        return bot.send_message(m.chat.id, "📭 Пусто", reply_markup=kb())
    txt = "📋 История:\n" + "\n".join(
        [
            f"{r['created_at'][:10]} | {r['type']}: {r['amount']}₽ ({r['category']})"
            for r in rows
        ]
    )
    bot.send_message(m.chat.id, txt, reply_markup=kb())


@bot.message_handler(commands=["categories"])
@bot.message_handler(func=lambda m: m.text == "📊 Категории")
def cats(m):
    exp = get_categories_summary(m.from_user.id, "expense")
    if not exp:
        return bot.send_message(m.chat.id, "📭 Нет расходов", reply_markup=kb())
    txt = "📊 Расходы:\n" + "\n".join(
        [f"• {r['category']}: {r['total']}₽" for r in exp]
    )
    bot.send_message(m.chat.id, txt, reply_markup=kb())


@bot.message_handler(commands=["undo"])
def undo(m):
    if delete_last(m.from_user.id):
        bot.send_message(
            m.chat.id,
            f"↩️ Удалено. Баланс: {get_balance(m.from_user.id)}₽",
            reply_markup=kb(),
        )
    else:
        bot.send_message(m.chat.id, "❌ Нечего удалять", reply_markup=kb())


@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.send_message(m.chat.id, "Не понял. Используй /help", reply_markup=kb())


def send_reminders():
    import datetime

    now = datetime.datetime.now()
    for u in get_all_reminder_users(now.hour, now.minute):
        try:
            bot.send_message(
                u["chat_id"],
                "🔔 Напоминание: запиши расходы/доходы за сегодня!",
                reply_markup=inline_kb(u["user_id"]),
            )
        except:
            pass


def run_webhook(port, base):
    wp = base.rstrip("/") + "/webhook"
    bot.remove_webhook()
    bot.set_webhook(f"https://{PRIMARY_DOMAIN}{wp}")
    print(f"✅ Webhook: {wp} | MiniApp: {MINIAPP_URL}")
    sched = BackgroundScheduler()
    sched.add_job(send_reminders, "cron", minute="*")
    sched.start()

    @app.route(wp, methods=["POST"])
    def wh():
        bot.process_new_updates(
            [telebot.types.Update.de_json(request.get_json(force=True))]
        )
        return "", 200

    try:
        app.run(host="0.0.0.0", port=port)
    finally:
        sched.shutdown()


def run_polling():
    print("✅ Polling запущен | MiniApp:", MINIAPP_URL)
    sched = BackgroundScheduler()
    sched.add_job(send_reminders, "cron", minute="*")
    sched.start()
    try:
        bot.infinity_polling()
    finally:
        sched.shutdown()


if __name__ == "__main__":
    init_db()
    PORT = int(os.environ.get("PORT", 0))
    BASE = os.environ.get("BASE_PATH", "/bot")
    run_webhook(PORT, BASE) if PORT else run_polling()
