"""📥 Импорт банковских выписок с помощью ИИ (GigaChat)"""
import io
import json
import os
import re

from gigachat import GigaChat

from db import add_transaction, get_history

GIGACHAT_KEY = os.environ.get("GIGACHAT_KEY", "")

CATEGORIES = [
    "Продукты", "Транспорт", "Кафе и рестораны", "Здоровье",
    "Одежда", "Развлечения", "Дом", "Связь", "Образование",
    "Зарплата", "Переводы", "Копилка", "Прочее",
]

PROMPT_TEMPLATE = """Ты — помощник финансового бота. Ниже — строки из банковской выписки.
Для каждой строки-операции определи: дату, сумму, тип (income — доход, expense — расход), краткое описание и категорию из списка: {cats}.
Ответь СТРОГО JSON-массивом без пояснений:
[{{"date": "2026-07-05", "amount": 123.45, "type": "expense", "desc": "Пятёрочка", "category": "Продукты"}}]
Строки, которые не являются операциями (заголовки, итоги, служебные), игнорируй.
Сумму указывай положительным числом.

Строки выписки:
{rows}"""


def _ask_ai(text):
    print("🤖 [ИМПОРТ] Запрашиваю нейросеть...", flush=True)
    with GigaChat(credentials=GIGACHAT_KEY, verify_ssl_certs=False, timeout=30) as g:
        resp = g.chat(text)
    print("✅ [ИМПОРТ] Нейросеть ответила", flush=True)
    return resp.choices[0].message.content


def _parse_json(text):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def read_xlsx(file_bytes):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    return lines


def read_csv(file_bytes):
    import csv
    text = None
    for enc in ("utf-8-sig", "cp1251", "utf-8"):
        try:
            text = file_bytes.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        return []
    lines = []
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row if c.strip()]
        if cells:
            lines.append(" | ".join(cells))
    return lines


def analyze(lines):
    items = []
    for i in range(0, len(lines), 100):
        chunk = lines[i:i + 100]
        prompt = PROMPT_TEMPLATE.format(cats=", ".join(CATEGORIES), rows="\n".join(chunk))
        items.extend(_parse_json(_ask_ai(prompt)))
    return items


def register(bot):
    @bot.message_handler(content_types=["document"])
    def handle_document(m):
        print(f"📥 [ИМПОРТ] Получен файл: {m.document.file_name}", flush=True)
        low = (m.document.file_name or "").lower()
        if not (low.endswith(".xlsx") or low.endswith(".csv")):
            bot.send_message(
                m.chat.id,
                "📎 Пока понимаю выписки в формате Excel (.xlsx) или CSV. Скачайте выписку в Excel и пришлите снова 🙂",
            )
            return
        if not GIGACHAT_KEY:
            bot.send_message(m.chat.id, "⚠️ Не настроен ключ ИИ (GIGACHAT_KEY) на сервере.")
            return

        bot.send_message(
            m.chat.id,
            "⏳ Получил файл! Читаю выписку и раскидываю по категориям — это займёт до минуты…",
        )
        try:
            file_info = bot.get_file(m.document.file_id)
            resp = bot.download_file(file_info.file_path)
            if isinstance(resp, bytes):
                file_bytes = resp
            elif hasattr(resp, "read"):
                file_bytes = resp.read()
            else:
                file_bytes = resp.content

            lines = read_xlsx(file_bytes) if low.endswith(".xlsx") else read_csv(file_bytes)
            print(f"📥 [ИМПОРТ] Строк из файла: {len(lines)}", flush=True)
            lines = lines[:600]
            if not lines:
                bot.send_message(m.chat.id, "🤔 Не смог прочитать ни одной строки из файла.")
                return

            items = analyze(lines)
            print(f"🧠 [ИМПОРТ] Нейросеть распознала операций: {len(items)}", flush=True)
            if not items:
                bot.send_message(
                    m.chat.id,
                    "😕 Не нашёл в файле строк, похожих на операции. Убедитесь, что это выписка в Excel/CSV.",
                )
                return

            existing = get_history(m.from_user.id, 5000)
            seen = set(
                (r["created_at"], round(float(r["amount"]), 2), (r["note"] or ""))
                for r in existing
            )

            added, skipped = 0, 0
            totals = {}
            for it in items:
                try:
                    date = str(it.get("date", ""))[:10]
                    if len(date) != 10 or "-" not in date:
                        continue
                    amount = abs(float(it.get("amount", 0)))
                    if amount <= 0:
                        continue
                    ttype = "income" if str(it.get("type")) == "income" else "expense"
                    desc = str(it.get("desc", ""))[:100]
                    cat = str(it.get("category", "Прочее"))
                    if cat not in CATEGORIES:
                        cat = "Прочее"
                    created = date + " 00:00:00"
                    key = (created, round(amount, 2), desc)
                    if key in seen:
                        skipped += 1
                        continue
                    seen.add(key)
                    add_transaction(m.from_user.id, ttype, amount, cat, desc)
                    added += 1
                    if ttype == "expense":
                        totals[cat] = totals.get(cat, 0) + amount
                except Exception:
                    continue

            report = f"✅ Готово! Добавлено операций: {added}, пропущено дубликатов: {skipped}."
            if totals:
                top = sorted(totals.items(), key=lambda kv: -kv[1])[:5]
                top_txt = "\n".join("• {}: {:,} ₽".format(c, round(s)).replace(",", " ") for c, s in top)
                report += f"\n\n📊 Топ расходов:\n{top_txt}"
            bot.send_message(m.chat.id, report)
        except Exception as e:
            print(f"❌ [ИМПОРТ] Ошибка: {e}", flush=True)
            bot.send_message(m.chat.id, f"⚠️ Не получилось разобрать выписку: {e}")
