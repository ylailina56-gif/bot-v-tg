import os
import re
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo,
)
from db import (
    init_db, add_transaction, get_balance, get_history,
    get_categories_summary, delete_last, get_monthly_summary,
    save_user, set_reminder, get_reminder, get_all_reminder_users,
)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в переменных окружения")

bot = telebot.TeleBot(TOKEN)

REPLIT_DOMAINS = os.environ.get("REPLIT_DOMAINS", "")
PRIMARY_DOMAIN = REPLIT_DOMAINS.split(",")[0] if REPLIT_DOMAINS else ""
MINIAPP_URL = f"https://{PRIMARY_DOMAIN}/miniapp/" if PRIMARY_DOMAIN else ""

HELP_TEXT = """
💰 *Бот учёта финансов*

*Добавить транзакцию:*
`/add доход 5000 Зарплата`
`/add расход 350 Еда`
`/add расход 1200 Транспорт заправка`

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


def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("💳 Баланс"),
        KeyboardButton("📋 История"),
        KeyboardButton("📊 Категории"),
        KeyboardButton("📅 Месяц"),
    ]
    if MINIAPP_URL:
        buttons.append(KeyboardButton("📱 Открыть приложение", web_app=WebAppInfo(url=MINIAPP_URL)))
    kb.add(*buttons)
    return kb


def app_inline_button(user_id=None):
    if not MINIAPP_URL:
        return None
    url = f"{MINIAPP_URL}?uid={user_id}" if user_id else MINIAPP_URL
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📱 Открыть Mini App", web_app=WebAppInfo(url=url)))
    return kb


def send_daily_reminder():
    """Runs every minute; sends reminders to users whose time matches now."""
    import datetime
    now = datetime.datetime.now()
    users = get_all_reminder_users(now.hour, now.minute)
    for u in users:
        try:
            bot.send_message(
                u["chat_id"],
                "🔔 *Напоминание!*\n\nНе забудь записать расходы и доходы за сегодня.\nИспользуй /add или открой Mini App 📱",
                parse_mode="Markdown",
                reply_markup=app_inline_button(u.get("user_id"))
            )
        except Exception:
            pass


@bot.message_handler(commands=["start"])
def cmd_start(message):
    save_user(message.from_user.id, message.chat.id)
    name = message.from_user.first_name or "друг"
    uid = message.from_user.id
    bot.send_message(
        message.chat.id,
        f"Привет, {name}! 👋\n\nЯ помогу тебе следить за доходами и расходами.\n\n{HELP_TEXT}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    if MINIAPP_URL:
        bot.send_message(
            message.chat.id,
            "Нажми кнопку ниже, чтобы открыть визуальный интерфейс:",
            reply_markup=app_inline_button(uid)
        )


@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.send_message(message.chat.id, HELP_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())


@bot.message_handler(commands=["app"])
def cmd_app(message):
    kb = app_inline_button(message.from_user.id)
    if kb:
        bot.send_message(message.chat.id, "Открыть визуальный интерфейс:", reply_markup=kb)
    else:
        bot.send_message(message.chat.id, "Mini App недоступен в данный момент.")


@bot.message_handler(commands=["remind"])
def cmd_remind(message):
    save_user(message.from_user.id, message.chat.id)
    parts = message.text.strip().split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""

    if arg.lower() == "off":
        set_reminder(message.from_user.id, None, None)
        bot.send_message(message.chat.id, "🔕 Напоминания отключены.", reply_markup=main_keyboard())
        return

    match = re.fullmatch(r"(\d{1,2}):(\d{2})", arg)
    if not match:
        bot.send_message(
            message.chat.id,
            "❌ Неверный формат.\n\n"
            "Примеры:\n`/remind 21:00` — напоминание в 21:00\n`/remind off` — отключить",
            parse_mode="Markdown"
        )
        return

    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        bot.send_message(message.chat.id, "❌ Некорректное время. Укажи часы 0–23, минуты 0–59.")
        return

    set_reminder(message.from_user.id, hour, minute)
    bot.send_message(
        message.chat.id,
        f"✅ Напоминание установлено на *{hour:02d}:{minute:02d}* каждый день.\n"
        f"Чтобы отключить: `/remind off`",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["add"])
def cmd_add(message):
    save_user(message.from_user.id, message.chat.id)
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.send_message(
            message.chat.id,
            "❌ Неверный формат. Примеры:\n"
            "`/add доход 5000 Зарплата`\n"
            "`/add расход 350 Еда`",
            parse_mode="Markdown"
        )
        return

    _, ttype_raw, amount_raw, rest = parts
    category_parts = rest.split(maxsplit=1)
    category = category_parts[0]
    note = category_parts[1] if len(category_parts) > 1 else ""

    ttype_map = {
        "доход": "income", "income": "income", "приход": "income", "+": "income",
        "расход": "expense", "expense": "expense", "трата": "expense", "-": "expense",
    }
    ttype = ttype_map.get(ttype_raw.lower())
    if not ttype:
        bot.send_message(message.chat.id, "❌ Тип должен быть: `доход` или `расход`", parse_mode="Markdown")
        return

    try:
        amount = float(amount_raw.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "❌ Сумма должна быть положительным числом")
        return

    add_transaction(message.from_user.id, ttype, amount, category, note)
    balance = get_balance(message.from_user.id)

    icon = "📈" if ttype == "income" else "📉"
    label = "Доход" if ttype == "income" else "Расход"
    bot.send_message(
        message.chat.id,
        f"{icon} *{label} записан*\n"
        f"Сумма: *{amount:,.2f} ₽*\n"
        f"Категория: {category}"
        + (f"\nЗаметка: {note}" if note else "") +
        f"\n\n💰 Текущий баланс: *{balance:,.2f} ₽*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["balance"])
@bot.message_handler(func=lambda m: m.text == "💳 Баланс")
def cmd_balance(message):
    balance = get_balance(message.from_user.id)
    month = get_monthly_summary(message.from_user.id)
    income = month["income"] if month else 0
    expense = month["expense"] if month else 0

    emoji = "🟢" if balance >= 0 else "🔴"
    bot.send_message(
        message.chat.id,
        f"{emoji} *Текущий баланс: {balance:,.2f} ₽*\n\n"
        f"📅 *Этот месяц:*\n"
        f"  📈 Доходы: {income:,.2f} ₽\n"
        f"  📉 Расходы: {expense:,.2f} ₽",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["history"])
@bot.message_handler(func=lambda m: m.text == "📋 История")
def cmd_history(message):
    rows = get_history(message.from_user.id, limit=10)
    if not rows:
        bot.send_message(message.chat.id, "📭 Транзакций пока нет. Добавьте первую командой /add", reply_markup=main_keyboard())
        return

    lines = ["📋 *Последние операции:*\n"]
    for r in rows:
        icon = "📈" if r["type"] == "income" else "📉"
        date = r["created_at"][:10]
        note = f" — {r['note']}" if r["note"] else ""
        lines.append(f"{icon} {date} | *{r['amount']:,.2f} ₽* | {r['category']}{note}")

    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown", reply_markup=main_keyboard())


@bot.message_handler(commands=["categories"])
@bot.message_handler(func=lambda m: m.text == "📊 Категории")
def cmd_categories(message):
    expenses = get_categories_summary(message.from_user.id, "expense")
    incomes = get_categories_summary(message.from_user.id, "income")

    if not expenses and not incomes:
        bot.send_message(message.chat.id, "📭 Данных пока нет. Добавьте транзакцию командой /add", reply_markup=main_keyboard())
        return

    lines = ["📊 *Сводка по категориям:*\n"]

    if expenses:
        total_exp = sum(r["total"] for r in expenses)
        lines.append("📉 *Расходы:*")
        for r in expenses:
            pct = r["total"] / total_exp * 100
            lines.append(f"  • {r['category']}: {r['total']:,.2f} ₽ ({pct:.0f}%)")
        lines.append(f"  *Итого: {total_exp:,.2f} ₽*\n")

    if incomes:
        total_inc = sum(r["total"] for r in incomes)
        lines.append("📈 *Доходы:*")
        for r in incomes:
            pct = r["total"] / total_inc * 100
            lines.append(f"  • {r['category']}: {r['total']:,.2f} ₽ ({pct:.0f}%)")
        lines.append(f"  *Итого: {total_inc:,.2f} ₽*")

    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="Markdown", reply_markup=main_keyboard())


@bot.message_handler(commands=["month"])
@bot.message_handler(func=lambda m: m.text == "📅 Месяц")
def cmd_month(message):
    month = get_monthly_summary(message.from_user.id)
    income = month["income"] if month else 0
    expense = month["expense"] if month else 0
    diff = income - expense

    emoji = "🟢" if diff >= 0 else "🔴"
    bot.send_message(
        message.chat.id,
        f"📅 *Итоги текущего месяца:*\n\n"
        f"📈 Доходы: *{income:,.2f} ₽*\n"
        f"📉 Расходы: *{expense:,.2f} ₽*\n"
        f"{emoji} Итог: *{diff:+,.2f} ₽*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=["undo"])
def cmd_undo(message):
    if delete_last(message.from_user.id):
        balance = get_balance(message.from_user.id)
        bot.send_message(
            message.chat.id,
            f"↩️ Последняя запись удалена.\n💰 Текущий баланс: *{balance:,.2f} ₽*",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    else:
        bot.send_message(message.chat.id, "❌ Нет записей для удаления", reply_markup=main_keyboard())


@bot.message_handler(commands=["stats"])
def cmd_stats(message):
    import sqlite3, json, urllib.request, urllib.error
    db_path = os.path.join(os.path.dirname(__file__), "finance.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT date(created_at,'localtime') as day, category, SUM(amount) as total
        FROM transactions
        WHERE user_id=? AND type='expense'
          AND date(created_at,'localtime') >= date('now','-6 days','localtime')
        GROUP BY day, category ORDER BY day
    """, (message.from_user.id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, "📭 Нет расходов за последние 7 дней.", reply_markup=main_keyboard())
        return

    days = sorted(set(r["day"] for r in rows))
    labels = [d[5:].replace("-", ".") for d in days]
    cat_totals = {}
    for r in rows:
        cat_totals[r["category"]] = cat_totals.get(r["category"], 0) + r["total"]
    top_cats = sorted(cat_totals, key=lambda c: cat_totals[c], reverse=True)[:5]
    other_cats = [c for c in cat_totals if c not in top_cats]
    colors = ["#4F8EF7", "#FF6B6B", "#4CAF50", "#FF9800", "#9C27B0", "#78909C"]

    datasets = []
    for i, cat in enumerate(top_cats):
        datasets.append({
            "label": cat,
            "backgroundColor": colors[i],
            "data": [round(next((r["total"] for r in rows if r["day"]==d and r["category"]==cat), 0)) for d in days],
        })
    if other_cats:
        datasets.append({
            "label": "Другие",
            "backgroundColor": colors[5],
            "data": [round(sum(r["total"] for r in rows if r["day"]==d and r["category"] in other_cats)) for d in days],
        })

    chart_cfg = {
        "type": "bar",
        "data": {"labels": labels, "datasets": datasets},
        "options": {
            "plugins": {"title": {"display": True, "text": "Расходы за 7 дней (₽)", "font": {"size": 16}}, "legend": {"position": "bottom"}},
            "scales": {"x": {"stacked": True}, "y": {"stacked": True}},
        },
    }
    total_exp = sum(r["total"] for r in rows)
    caption = "📊 *Расходы за 7 дней*\n\n" + "\n".join(
        f"• {c}: {cat_totals[c]:,.2f} ₽"
        for c in sorted(cat_totals, key=lambda x: cat_totals[x], reverse=True)
    ) + f"\n\n💸 *Итого: {total_exp:,.2f} ₽*"

    try:
        payload = json.dumps({"chart": chart_cfg, "width": 600, "height": 400, "format": "png", "backgroundColor": "white"}).encode()
        req = urllib.request.Request("https://quickchart.io/chart", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            img_bytes = resp.read()
        import io
        bot.send_photo(message.chat.id, io.BytesIO(img_bytes), caption=caption, parse_mode="Markdown", reply_markup=main_keyboard())
    except Exception:
        bot.send_message(message.chat.id, caption, parse_mode="Markdown", reply_markup=main_keyboard())


@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(
        message.chat.id,
        "Не понял команду. Используй /help для справки.",
        reply_markup=main_keyboard()
    )


def run_polling():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_daily_reminder, "cron", minute="*")
    scheduler.start()
    print("Бот запущен в режиме polling ✅")
    if MINIAPP_URL:
        print(f"Mini App URL: {MINIAPP_URL}")
    try:
        bot.infinity_polling()
    finally:
        scheduler.shutdown()


def run_webhook(port: int, base_path: str):
    from flask import Flask, request as flask_request
    from apscheduler.schedulers.background import BackgroundScheduler

    flask_app = Flask(__name__)
    webhook_path = base_path.rstrip("/") + "/webhook"
    webhook_url = f"https://{PRIMARY_DOMAIN}{webhook_path}"

    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"Бот запущен в режиме webhook ✅")
    print(f"Webhook URL: {webhook_url}")
    if MINIAPP_URL:
        print(f"Mini App URL: {MINIAPP_URL}")

    scheduler = BackgroundScheduler()
    scheduler.add_job(send_daily_reminder, "cron", minute="*")
    scheduler.start()

    @flask_app.route(webhook_path, methods=["POST"])
    def webhook():
        update = telebot.types.Update.de_json(flask_request.get_json(force=True))
        bot.process_new_updates([update])
        return "", 200

    @flask_app.route(base_path.rstrip("/") + "/healthz", methods=["GET"])
    def healthz():
        return {"status": "ok"}, 200

    try:
        flask_app.run(host="0.0.0.0", port=port)
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    init_db()
    PORT = int(os.environ.get("PORT", 0))
    BASE_PATH = os.environ.get("BASE_PATH", "/bot")

    if PORT:
        run_webhook(PORT, BASE_PATH)
    else:
        run_polling()
