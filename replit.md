# Telegram Finance Bot

Telegram-бот для учёта личных финансов: доходы, расходы, баланс, история и сводки по категориям.

## Run & Operate

- `cd bot && python main.py` — запустить бота (workflow: "Telegram Finance Bot")
- Required env: `TELEGRAM_BOT_TOKEN` — токен бота от @BotFather

## Stack

- Python 3, pyTelegramBotAPI
- SQLite (файл `bot/finance.db`, создаётся автоматически)

## Where things live

- `bot/main.py` — основной файл бота, все команды и обработчики
- `bot/db.py` — работа с базой данных SQLite
- `bot/finance.db` — файл базы данных (создаётся при первом запуске)
- `bot/requirements.txt` — зависимости Python

## Product

Бот позволяет:
- Добавлять доходы и расходы (`/add`)
- Просматривать текущий баланс (`/balance`)
- Смотреть последние 10 операций (`/history`)
- Получать сводку по категориям (`/categories`)
- Получать итоги за текущий месяц (`/month`)
- Отменять последнюю запись (`/undo`)
- Быстрые кнопки в меню бота

## User preferences

- Интерфейс бота на русском языке

## Gotchas

- База данных хранится в `bot/finance.db` — не удалять
- Каждый пользователь видит только свои данные (по user_id)
