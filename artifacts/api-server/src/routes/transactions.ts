import { Router } from "express";
import Database from "better-sqlite3";
import path from "path";
import { mkdirSync } from "fs";
import {
  ListTransactionsQueryParams,
  CreateTransactionBody,
  DeleteTransactionParams,
  GetBalanceQueryParams,
  GetCategorySummaryQueryParams,
  GetMonthlySummaryQueryParams,
  GetLimitsQueryParams,
  SetLimitBody,
  DeleteLimitParams,
} from "@workspace/api-zod";

// In production cwd = workspace root; in dev cwd = artifacts/api-server
const WS_ROOT = process.cwd().includes("api-server")
  ? path.resolve(process.cwd(), "../..")
  : process.cwd();
const DB_PATH = path.resolve(WS_ROOT, "bot/finance.db");
mkdirSync(path.dirname(DB_PATH), { recursive: true });

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
  db.exec(`CREATE TABLE IF NOT EXISTS limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    monthly_limit REAL NOT NULL,
    UNIQUE(user_id, category)
  )`);
  return db;
}

const router = Router();

router.get("/transactions", (req, res) => {
  const parsed = ListTransactionsQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "user_id required" });
    return;
  }
  const { user_id, limit = 50 } = parsed.data;
  const db = getDb();
  const rows = db
    .prepare("SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?")
    .all(user_id, limit);
  db.close();
  res.json(rows);
});

router.post("/transactions", (req, res) => {
  const parsed = CreateTransactionBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.flatten() });
    return;
  }
  const { user_id, type, amount, category, note = "" } = parsed.data;
  const db = getDb();
  const result = db
    .prepare("INSERT INTO transactions (user_id, type, amount, category, note) VALUES (?, ?, ?, ?, ?)")
    .run(user_id, type, amount, category, note);
  const row = db.prepare("SELECT * FROM transactions WHERE id = ?").get(result.lastInsertRowid);
  db.close();
  res.status(201).json(row);
});

router.delete("/transactions/:id", (req, res) => {
  const parsed = DeleteTransactionParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) {
    res.status(400).json({ error: "invalid id" });
    return;
  }
  const db = getDb();
  const result = db.prepare("DELETE FROM transactions WHERE id = ?").run(parsed.data.id);
  db.close();
  res.json({ success: result.changes > 0 });
});

router.get("/summary/balance", (req, res) => {
  const parsed = GetBalanceQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "user_id required" });
    return;
  }
  const { user_id } = parsed.data;
  const db = getDb();
  const row = db
    .prepare(
      `SELECT
        COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) AS total_income,
        COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS total_expense
       FROM transactions WHERE user_id = ?`
    )
    .get(user_id) as { total_income: number; total_expense: number };
  db.close();
  res.json({
    balance: row.total_income - row.total_expense,
    total_income: row.total_income,
    total_expense: row.total_expense,
  });
});

router.get("/summary/categories", (req, res) => {
  const parsed = GetCategorySummaryQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "user_id required" });
    return;
  }
  const { user_id } = parsed.data;
  const db = getDb();
  const expenses = db
    .prepare(
      `SELECT category, SUM(amount) as total FROM transactions
       WHERE user_id = ? AND type = 'expense'
       GROUP BY category ORDER BY total DESC`
    )
    .all(user_id) as { category: string; total: number }[];
  const incomes = db
    .prepare(
      `SELECT category, SUM(amount) as total FROM transactions
       WHERE user_id = ? AND type = 'income'
       GROUP BY category ORDER BY total DESC`
    )
    .all(user_id) as { category: string; total: number }[];
  db.close();
  res.json({ expenses, incomes });
});

router.get("/summary/monthly", (req, res) => {
  const parsed = GetMonthlySummaryQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "user_id required" });
    return;
  }
  const { user_id } = parsed.data;
  const db = getDb();
  const row = db
    .prepare(
      `SELECT
        COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) AS income,
        COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS expense
       FROM transactions
       WHERE user_id = ?
         AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now', 'localtime')`
    )
    .get(user_id) as { income: number; expense: number };
  db.close();
  res.json({ income: row.income, expense: row.expense, net: row.income - row.expense });
});

// ── Limits ──────────────────────────────────────────────────────────────────

router.get("/limits", (req, res) => {
  const parsed = GetLimitsQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "user_id required" });
    return;
  }
  const { user_id } = parsed.data;
  const db = getDb();
  const rows = db
    .prepare("SELECT id, user_id, category, monthly_limit FROM limits WHERE user_id = ? ORDER BY category")
    .all(user_id);
  db.close();
  res.json(rows);
});

router.post("/limits", (req, res) => {
  const parsed = SetLimitBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.flatten() });
    return;
  }
  const { user_id, category, monthly_limit } = parsed.data;
  const db = getDb();
  db.prepare(
    `INSERT INTO limits (user_id, category, monthly_limit) VALUES (?, ?, ?)
     ON CONFLICT(user_id, category) DO UPDATE SET monthly_limit = excluded.monthly_limit`
  ).run(user_id, category, monthly_limit);
  const row = db
    .prepare("SELECT id, user_id, category, monthly_limit FROM limits WHERE user_id = ? AND category = ?")
    .get(user_id, category);
  db.close();
  res.json(row);
});

router.delete("/limits/:id", (req, res) => {
  const parsed = DeleteLimitParams.safeParse({ id: Number(req.params.id) });
  if (!parsed.success) {
    res.status(400).json({ error: "invalid id" });
    return;
  }
  const db = getDb();
  const result = db.prepare("DELETE FROM limits WHERE id = ?").run(parsed.data.id);
  db.close();
  res.json({ success: result.changes > 0 });
});

// ── Data import (merge users) ────────────────────────────────────────────────

router.post("/import-data", (req, res) => {
  const { to_user_id, from_user_id } = req.body as { to_user_id?: number; from_user_id?: number };
  if (!to_user_id || !from_user_id || to_user_id === from_user_id) {
    res.status(400).json({ error: "to_user_id and from_user_id required and must differ" });
    return;
  }
  const db = getDb();
  const txCount = (db.prepare("SELECT COUNT(*) AS n FROM transactions WHERE user_id=?").get(from_user_id) as { n: number }).n;
  if (txCount === 0) {
    db.close();
    res.json({ imported: 0, message: "Нет данных для импорта" });
    return;
  }
  db.prepare("UPDATE transactions SET user_id=? WHERE user_id=?").run(to_user_id, from_user_id);
  db.prepare("UPDATE OR IGNORE limits SET user_id=? WHERE user_id=?").run(to_user_id, from_user_id);
  db.prepare("DELETE FROM limits WHERE user_id=?").run(from_user_id);
  db.close();
  res.json({ imported: txCount });
});

export default router;
