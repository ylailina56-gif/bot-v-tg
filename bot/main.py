import os
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

# Твой рабочий токен, который мы нашли!
TOKEN = "8703775745:AAGt78MkW2dcBDm5AskVfNCEjctQ63H-Xmc"

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
`/add расход 1200 Транспорт заправка`

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
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = KeyboardButton("💳 Баланс")
    btn2 = KeyboardButton("📋 История")
    btn3 = KeyboardButton("📊 Категории")
    btn4 = KeyboardButton("📅 Месяц")
    markup.add(btn1, btn2, btn3, btn4)

    if MINIAPP_URL:
        web_app = WebAppInfo(MINIAPP_URL)
        btn_app = KeyboardButton("📱 Открыть Mini App", web_app=web_app)
        markup.add(btn_app)
    return markup

@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    save_user(message.from_user.id, message.from_user.username)
    welcome = f"Привет, Юля! 👋\n\nЯ помогу тебе следить за доходами и расходами.\n\n{HELP_TEXT}"
    bot.send_message(message.chat.id, welcome, parse_mode="Markdown", reply_markup=main_keyboard())

@bot.message_handler(commands=["add"])
def cmd_add(message):
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            bot.reply_to(message, "❌ Неверный формат! Используй:\n`/add расход 350 Еда`", parse_mode="Markdown")
            return
        t_type = parts[1].lower()
        amount = float(parts[2])
        category = parts[3]

        if t_type not in ["доход", "расход"]:
            bot.reply_to(message, "❌ Укажи `доход` или `расход`.")
            return

        add_transaction(message.from_user.id, t_type, amount, category)
        bot.reply_to(message, f"✅ Записано: {t_type} {amount} руб. в '{category}'")
    except:
        bot.reply_to(message, "❌ Ошибка добавления. Сумма должна быть числом.")

@bot.message_handler(commands=["undo"])
def cmd_undo(message):
    if delete_last(message.from_user.id):
        bot.send_message(message.chat.id, "🗑 Последняя запись успешно удалена!")
    else:
        bot.send_message(message.chat.id, "В базе данных пока нет ваших записей.")

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    user_id = message.from_user.id
    if message.text == "💳 Баланс" or message.text == "/balance":
        balance = get_balance(user_id)
        bot.send_message(message.chat.id, f"💳 *Текущий баланс:* {balance} руб.", parse_mode="Markdown")
    elif message.text == "📋 История" or message.text == "/history":
        history = get_history(user_id)
        bot.send_message(message.chat.id, history, parse_mode="Markdown")
    elif message.text == "📊 Категории" or message.text == "/categories":
        summary = get_categories_summary(user_id)
        bot.send_message(message.chat.id, summary, parse_mode="Markdown")
    elif message.text == "📅 Месяц" or message.text == "/month":
        summary = get_monthly_summary(user_id)
        bot.send_message(message.chat.id, summary, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Используй кнопки меню или команды.")
@app.route('/api/add', methods=['POST'])
def api_add_transaction():
    try:
        data = request.json
        user_id = data.get('user_id')
        t_type = data.get('type', 'расход').lower()
        amount = float(data.get('amount', 0))
        category = data.get('category', 'Разное')

        # Записываем в нашу базу данных
        add_transaction(user_id, t_type, amount, category)
        return {"status": "success"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400
if __name__ == "__main__":
    init_db()
    # Запускаем бота в фоновом потоке, чтобы он не вешал Flask
    bot.remove_webhook()
    t = threading.Thread(target=lambda: bot.infinity_polling(timeout=10, long_polling_timeout=5), daemon=True)
    t.start()

    # Запускаем Flask на порту 8080 для Mini App
    app.run(host="0.0.0.0", port=8080)