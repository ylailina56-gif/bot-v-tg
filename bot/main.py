import os
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo,
)
from db import init_db, add_transaction, get_balance, get_history, get_categories_summary, delete_last, get_monthly_summary

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан в переменных окружения")

bot = telebot.TeleBot(TOKEN)

REPLIT_DOMAINS = os.environ.get("REPLIT_DOMAINS", "")
MINIAPP_URL = f"https://{REPLIT_DOMAINS.split(',')[0]}/miniapp/" if REPLIT_DOMAINS else ""

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


@bot.message_handler(commands=["start"])
def cmd_start(message):
    init_db()
    name = message.from_user.first_name or "друг"
    kb = app_inline_button()
    bot.send_message(
        message.chat.id,
        f"Привет, {name}! 👋\n\nЯ помогу тебе следить за доходами и расходами.\n\n{HELP_TEXT}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    if kb:
        bot.send_message(
            message.chat.id,
            "Также доступен визуальный интерфейс:",
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
        bot.send_message(message.chat.id, "Mini App недоступен в данный момент.")


@bot.message_handler(commands=["add"])
def cmd_add(message):
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


@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(
        message.chat.id,
        "Не понял команду. Используй /help для справки.",
        reply_markup=main_keyboard()
    )


if __name__ == "__main__":
    init_db()
    print("Бот запущен ✅")
    if MINIAPP_URL:
        print(f"Mini App URL: {MINIAPP_URL}")
    bot.infinity_polling()
