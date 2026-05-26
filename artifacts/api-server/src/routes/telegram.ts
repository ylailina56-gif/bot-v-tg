import { Router } from "express";
import Database from "better-sqlite3";
import path from "path";
import { mkdirSync } from "fs";

const WS_ROOT = process.cwd().endsWith("api-server")
  ? path.resolve(process.cwd(), "../..")
  : process.cwd();
const DB_PATH = path.resolve(WS_ROOT, "bot/finance.db");
mkdirSync(path.dirname(DB_PATH), { recursive: true });

const TOKEN = process.env["TELEGRAM_BOT_TOKEN"] || "";
const DOMAINS = process.env["REPLIT_DOMAINS"] || "";
const PRIMARY_DOMAIN = DOMAINS.split(",")[0] || "";
export const MINIAPP_URL = PRIMARY_DOMAIN ? `https://${PRIMARY_DOMAIN}/miniapp/` : "";

// ── Telegram API ─────────────────────────────────────────────────────────────

async function tg(method: string, body: object) {
  if (!TOKEN) return;
  try {
    await fetch(`https://api.telegram.org/bot${TOKEN}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (_) {}
}

function mainKeyboard() {
  const keyboard: object[][] = [
    [{ text: "💳 Баланс" }, { text: "📋 История" }],
    [{ text: "📊 Категории" }, { text: "📅 Месяц" }],
  ];
  if (MINIAPP_URL) {
    keyboard.push([{ text: "📱 Открыть приложение", web_app: { url: MINIAPP_URL } }]);
  }
  return { keyboard, resize_keyboard: true };
}

function appInlineKeyboard() {
  if (!MINIAPP_URL) return null;
  return { inline_keyboard: [[{ text: "📱 Открыть Mini App", web_app: { url: MINIAPP_URL } }]] };
}

async function reply(chatId: number, text: string, extra?: object) {
  await tg("sendMessage", { chat_id: chatId, text, parse_mode: "Markdown", ...extra });
}

const HELP_TEXT = `
💰 *Бот учёта финансов*

*Добавить транзакцию:*
\`/add доход 5000 Зарплата\`
\`/add расход 350 Еда\`
\`/add расход 1200 Транспорт заправка\`

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
`;

// ── Database helpers ──────────────────────────────────────────────────────────

function getDb() {
  const db = new Database(DB_PATH);
  db.exec(`CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('income','expense')),
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    note TEXT,
    created_at DATETIME DEFAULT (datetime('now','localtime'))
  )`);
  db.exec(`CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    remind_hour INTEGER,
    remind_minute INTEGER
  )`);
  db.exec(`CREATE TABLE IF NOT EXISTS limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    monthly_limit REAL NOT NULL,
    UNIQUE(user_id, category)
  )`);
  return db;
}

function dbBalance(userId: number) {
  const db = getDb();
  const row = db.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END),0) AS inc,
      COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) AS exp
    FROM transactions WHERE user_id=?
  `).get(userId) as { inc: number; exp: number };
  const month = db.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END),0) AS inc,
      COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) AS exp
    FROM transactions WHERE user_id=? AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now','localtime')
  `).get(userId) as { inc: number; exp: number };
  db.close();
  return { balance: row.inc - row.exp, totalInc: row.inc, totalExp: row.exp, monthInc: month.inc, monthExp: month.exp };
}

function dbAddTx(userId: number, type: string, amount: number, category: string, note: string) {
  const db = getDb();
  db.prepare("INSERT INTO transactions(user_id,type,amount,category,note) VALUES(?,?,?,?,?)").run(userId, type, amount, category, note);
  db.close();
}

function dbHistory(userId: number) {
  const db = getDb();
  const rows = db.prepare("SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 10").all(userId) as any[];
  db.close();
  return rows;
}

function dbCategories(userId: number) {
  const db = getDb();
  const exp = db.prepare(`SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='expense' GROUP BY category ORDER BY total DESC`).all(userId) as any[];
  const inc = db.prepare(`SELECT category, SUM(amount) as total FROM transactions WHERE user_id=? AND type='income' GROUP BY category ORDER BY total DESC`).all(userId) as any[];
  db.close();
  return { exp, inc };
}

function dbMonthly(userId: number) {
  const db = getDb();
  const row = db.prepare(`
    SELECT
      COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END),0) AS inc,
      COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0) AS exp
    FROM transactions WHERE user_id=? AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now','localtime')
  `).get(userId) as { inc: number; exp: number };
  db.close();
  return row;
}

function dbDeleteLast(userId: number) {
  const db = getDb();
  const row = db.prepare("SELECT id FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 1").get(userId) as any;
  if (!row) { db.close(); return false; }
  db.prepare("DELETE FROM transactions WHERE id=?").run(row.id);
  db.close();
  return true;
}

function dbSaveUser(userId: number, chatId: number) {
  const db = getDb();
  db.prepare("INSERT OR IGNORE INTO users(user_id,chat_id) VALUES(?,?)").run(userId, chatId);
  db.prepare("UPDATE users SET chat_id=? WHERE user_id=?").run(chatId, userId);
  db.close();
}

function dbSetReminder(userId: number, hour: number | null, minute: number | null) {
  const db = getDb();
  db.prepare("UPDATE users SET remind_hour=?, remind_minute=? WHERE user_id=?").run(hour, minute, userId);
  db.close();
}

export function dbGetReminderUsers(hour: number, minute: number) {
  const db = getDb();
  const rows = db.prepare("SELECT chat_id FROM users WHERE remind_hour=? AND remind_minute=?").all(hour, minute) as any[];
  db.close();
  return rows;
}

const fmt = (n: number) => n.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ── Command handlers ──────────────────────────────────────────────────────────

async function handleStart(chatId: number, userId: number, firstName: string) {
  dbSaveUser(userId, chatId);
  const name = firstName || "друг";
  await reply(chatId, `Привет, ${name}! 👋\n\nЯ помогу тебе следить за доходами и расходами.\n\n${HELP_TEXT}`, { reply_markup: mainKeyboard() });
  const inlineKb = appInlineKeyboard();
  if (inlineKb) {
    await reply(chatId, "Нажми кнопку ниже, чтобы открыть визуальный интерфейс:", { reply_markup: inlineKb });
  }
}

async function handleBalance(chatId: number, userId: number) {
  const d = dbBalance(userId);
  const emoji = d.balance >= 0 ? "🟢" : "🔴";
  await reply(chatId,
    `${emoji} *Текущий баланс: ${fmt(d.balance)} ₽*\n\n📅 *Этот месяц:*\n  📈 Доходы: ${fmt(d.monthInc)} ₽\n  📉 Расходы: ${fmt(d.monthExp)} ₽`,
    { reply_markup: mainKeyboard() });
}

async function handleHistory(chatId: number, userId: number) {
  const rows = dbHistory(userId);
  if (!rows.length) { await reply(chatId, "📭 Транзакций пока нет. Добавьте первую командой /add", { reply_markup: mainKeyboard() }); return; }
  const lines = ["📋 *Последние операции:*\n"];
  for (const r of rows) {
    const icon = r.type === "income" ? "📈" : "📉";
    const note = r.note ? ` — ${r.note}` : "";
    lines.push(`${icon} ${r.created_at.slice(0, 10)} | *${fmt(r.amount)} ₽* | ${r.category}${note}`);
  }
  await reply(chatId, lines.join("\n"), { reply_markup: mainKeyboard() });
}

async function handleCategories(chatId: number, userId: number) {
  const { exp, inc } = dbCategories(userId);
  if (!exp.length && !inc.length) { await reply(chatId, "📭 Данных пока нет. Добавьте транзакцию командой /add", { reply_markup: mainKeyboard() }); return; }
  const lines = ["📊 *Сводка по категориям:*\n"];
  if (exp.length) {
    const total = exp.reduce((s: number, r: any) => s + r.total, 0);
    lines.push("📉 *Расходы:*");
    for (const r of exp) lines.push(`  • ${r.category}: ${fmt(r.total)} ₽ (${Math.round(r.total / total * 100)}%)`);
    lines.push(`  *Итого: ${fmt(total)} ₽*\n`);
  }
  if (inc.length) {
    const total = inc.reduce((s: number, r: any) => s + r.total, 0);
    lines.push("📈 *Доходы:*");
    for (const r of inc) lines.push(`  • ${r.category}: ${fmt(r.total)} ₽ (${Math.round(r.total / total * 100)}%)`);
    lines.push(`  *Итого: ${fmt(total)} ₽*`);
  }
  await reply(chatId, lines.join("\n"), { reply_markup: mainKeyboard() });
}

async function handleMonth(chatId: number, userId: number) {
  const m = dbMonthly(userId);
  const diff = m.inc - m.exp;
  const emoji = diff >= 0 ? "🟢" : "🔴";
  await reply(chatId,
    `📅 *Итоги текущего месяца:*\n\n📈 Доходы: *${fmt(m.inc)} ₽*\n📉 Расходы: *${fmt(m.exp)} ₽*\n${emoji} Итог: *${diff >= 0 ? "+" : ""}${fmt(diff)} ₽*`,
    { reply_markup: mainKeyboard() });
}

async function handleAdd(chatId: number, userId: number, text: string) {
  const parts = text.trim().split(/\s+/);
  if (parts.length < 4) {
    await reply(chatId, "❌ Неверный формат. Примеры:\n`/add доход 5000 Зарплата`\n`/add расход 350 Еда`");
    return;
  }
  const [, typeRaw, amountRaw, ...rest] = parts;
  const catParts = rest;
  const category = catParts[0];
  const note = catParts.slice(1).join(" ");
  const typeMap: Record<string, string> = {
    "доход": "income", "income": "income", "приход": "income", "+": "income",
    "расход": "expense", "expense": "expense", "трата": "expense", "-": "expense",
  };
  const type = typeMap[typeRaw.toLowerCase()];
  if (!type) { await reply(chatId, "❌ Тип должен быть: `доход` или `расход`"); return; }
  const amount = parseFloat(amountRaw.replace(",", "."));
  if (isNaN(amount) || amount <= 0) { await reply(chatId, "❌ Сумма должна быть положительным числом"); return; }
  dbAddTx(userId, type, amount, category, note);
  const { balance } = dbBalance(userId);
  const icon = type === "income" ? "📈" : "📉";
  const label = type === "income" ? "Доход" : "Расход";
  await reply(chatId,
    `${icon} *${label} записан*\nСумма: *${fmt(amount)} ₽*\nКатегория: ${category}${note ? `\nЗаметка: ${note}` : ""}\n\n💰 Текущий баланс: *${fmt(balance)} ₽*`,
    { reply_markup: mainKeyboard() });
}

async function handleRemind(chatId: number, userId: number, text: string) {
  dbSaveUser(userId, chatId);
  const arg = text.trim().split(/\s+/).slice(1).join(" ").trim();
  if (arg.toLowerCase() === "off") {
    dbSetReminder(userId, null, null);
    await reply(chatId, "🔕 Напоминания отключены.", { reply_markup: mainKeyboard() });
    return;
  }
  const m = /^(\d{1,2}):(\d{2})$/.exec(arg);
  if (!m) { await reply(chatId, "❌ Формат: `/remind 21:00` или `/remind off`"); return; }
  const hour = parseInt(m[1]), minute = parseInt(m[2]);
  if (hour > 23 || minute > 59) { await reply(chatId, "❌ Некорректное время."); return; }
  dbSetReminder(userId, hour, minute);
  await reply(chatId, `✅ Напоминание установлено на *${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}* каждый день.\nЧтобы отключить: \`/remind off\``, { reply_markup: mainKeyboard() });
}

async function handleUndo(chatId: number, userId: number) {
  if (dbDeleteLast(userId)) {
    const { balance } = dbBalance(userId);
    await reply(chatId, `↩️ Последняя запись удалена.\n💰 Текущий баланс: *${fmt(balance)} ₽*`, { reply_markup: mainKeyboard() });
  } else {
    await reply(chatId, "❌ Нет записей для удаления", { reply_markup: mainKeyboard() });
  }
}

// ── Router ───────────────────────────────────────────────────────────────────

const router = Router();

router.post("/telegram", async (req, res) => {
  res.sendStatus(200); // always ack immediately
  try {
    const update = req.body;
    const msg = update?.message;
    if (!msg?.text) return;

    const chatId: number = msg.chat.id;
    const userId: number = msg.from?.id ?? chatId;
    const firstName: string = msg.from?.first_name ?? "";
    const text: string = msg.text;

    if (text.startsWith("/start")) { await handleStart(chatId, userId, firstName); return; }
    if (text.startsWith("/help")) { await reply(chatId, HELP_TEXT, { reply_markup: mainKeyboard() }); return; }
    if (text.startsWith("/add")) { await handleAdd(chatId, userId, text); return; }
    if (text.startsWith("/balance") || text === "💳 Баланс") { await handleBalance(chatId, userId); return; }
    if (text.startsWith("/history") || text === "📋 История") { await handleHistory(chatId, userId); return; }
    if (text.startsWith("/categories") || text === "📊 Категории") { await handleCategories(chatId, userId); return; }
    if (text.startsWith("/month") || text === "📅 Месяц") { await handleMonth(chatId, userId); return; }
    if (text.startsWith("/remind")) { await handleRemind(chatId, userId, text); return; }
    if (text.startsWith("/undo")) { await handleUndo(chatId, userId); return; }
    if (text.startsWith("/app")) {
      const kb = appInlineKeyboard();
      if (kb) await reply(chatId, "Открыть визуальный интерфейс:", { reply_markup: kb });
      return;
    }
    await reply(chatId, "Не понял команду. Используй /help для справки.", { reply_markup: mainKeyboard() });
  } catch (_) {}
});

export default router;
