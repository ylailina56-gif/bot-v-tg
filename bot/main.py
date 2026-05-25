import os
import re
import telebot
import threading
import time
from flask import Flask, request, send_from_directory
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
app = Flask(__name__)

REPLIT_DOMAINS = os.environ.get("REPLIT_DOMAINS", "")
APP_DOMAIN = REPLIT_DOMAINS.split(',')[0] if REPLIT_DOMAINS else ""
MINIAPP_URL = f"https://{APP_DOMAIN}/miniapp/" if APP_DOMAIN else ""

HELP_TEXT = """
💰 *Бот учёта финансов*

*Добавить транзакцию:*
`/add доход 5000 Зарплата`
`/add расход 350 Еда`
`/add расход 1200 Траспорт заправка`

*Просмотр данных:*
/balance — текущий баланс
/history — последние 10 операций
/month — сводка за текущий месяц
/categories — расходы по категориям

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

def app_inline_button():
    if not MINIAPP_URL:
        return None
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📱 Открыть Mini App", web_app=WebAppInfo(url=MINIAPP_URL)))
    return kb

# Раздача Mini App
@app.route('/miniapp/')
@app.route('/miniapp/<path:path>')
def serve_miniapp(path="index.html"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base_dir, 'dist')
    if not os.path.exists(dist_dir):
        dist_dir = os.path.join(os.path.dirname(base_dir), 'dist')
    if not os.path.exists(dist_dir):
        dist_dir = os.path.join(os.path.dirname(base_dir), 'src', 'dist')
    return send_from_directory(dist_dir, path)

@app.route("/")
def index():
    return "Сервер активен, бот работает автономно! 🚀", 200

# Фоновая функция, которая запустит бота в обход блокировок Replit
def run_bot_polling():
    while True:
        try:
            bot.remove_webhook()
            print("Запуск бота в автономном режиме...")
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Перезапуск бота после ошибки: {e}")
            time.sleep(5)

@bot.message_handler(commands=["start"])
def cmd_start(message):
    init_db()
    save_user(message.from_user.id, message.chat.id)
    name = message.from_user.first_name or "друг"

    bot.send_message(
        message.chat.id,
        f"Привет, {name}! 👋\n\nЯ помогу тебе следить за доходами и расходами.\n\n{HELP_TEXT}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

    kb = app_inline_button()
    if kb:
        bot.send_message(
            message.chat.id,
            "Нажми кнопку ниже, чтобы открыть визуальный интерфейс:",
            reply_markup=kb
        )

@bot.message_handler(commands=["help"])
def cmd_help(message):
    bot.send_message(message.chat.id, HELP_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(commands=["app"])
def cmd_app(message):
    kb = app_inline_button()
    if kb:
        bot.send_message(message.chat.id, "Открыть визуальный интерфейс:", reply_markup=kb)
    else:
        bot.send_message(message.chat.id, "Mini App недоступен.")

@bot.message_handler(commands=["add"])
def cmd_add(message):
    save_user(message.from_user.id, message.chat.id)
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.send_message(message.chat.id, "❌ Неверный формат. Используй /add", parse_mode="Markdown")
        return

    _, ttype_raw, amount_raw, rest = parts
    category_parts = rest.split(maxsplit=1)
    category = category_parts[0]
    note = category_parts[1] if len(category_parts) > 1 else ""

    ttype_map = {"доход": "income", "расход": "expense"}
    ttype = ttype_map.get(ttype_raw.lower())
    if not ttype:
        bot.send_message(message.chat.id, "❌ Тип должен быть: `доход` или `расход`")
        return

    try:
        amount = float(amount_raw.replace(",", "."))
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверная сумма")
        return

    add_transaction(message.from_user.id, ttype, amount, category, note)
    balance = get_balance(message.from_user.id)
    bot.send_message(message.chat.id, f"✅ Запись добавлена! Баланс: {balance:,.2f} ₽", reply_markup=main_keyboard())

@bot.message_handler(commands=["balance"])
@bot.message_handler(func=lambda m: m.text == "💳 Баланс")
def cmd_balance(message):
    balance = get_balance(message.from_user.id)
    bot.send_message(message.chat.id, f"💳 Текущий баланс: *{balance:,.2f} ₽*", parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(message.chat.id, "Используй кнопки меню или /help", reply_markup=main_keyboard())

if __name__ == "__main__":
    init_db()

    # Хитрый ход: запускаем бота в отдельном независимом потоке
    bot_thread = threading.Thread(target=run_bot_polling, daemon=True)
    bot_thread.start()

    print("Автономный запуск завершен! ✅")
    # Стартуем веб-сервер, который Replit обязан держать включенным
    app.run(host="0.0.0.0", port=8080)