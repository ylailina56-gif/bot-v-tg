import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "finance.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            note TEXT,
            created_at DATETIME DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            remind_hour INTEGER,
            remind_minute INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            monthly_limit REAL NOT NULL,
            UNIQUE(user_id, category)
        )
    """)
    conn.commit()
    conn.close()


def add_transaction(user_id: int, ttype: str, amount: float, category: str, note: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO transactions (user_id, type, amount, category, note) VALUES (?, ?, ?, ?, ?)",
        (user_id, ttype, amount, category, note)
    )
    conn.commit()
    conn.close()


def get_balance(user_id: int) -> float:
    conn = get_conn()
    row = conn.execute(
        """SELECT
            COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS balance
           FROM transactions WHERE user_id = ?""",
        (user_id,)
    ).fetchone()
    conn.close()
    return row["balance"] if row else 0.0


def get_history(user_id: int, limit: int = 10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


def get_categories_summary(user_id: int, ttype: str):
    conn = get_conn()
    rows = conn.execute(
        """SELECT category, SUM(amount) as total
           FROM transactions
           WHERE user_id = ? AND type = ?
           GROUP BY category
           ORDER BY total DESC""",
        (user_id, ttype)
    ).fetchall()
    conn.close()
    return rows


def delete_last(user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    if row:
        conn.execute("DELETE FROM transactions WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def get_monthly_summary(user_id: int):
    conn = get_conn()
    row = conn.execute(
        """SELECT
            COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS expense
           FROM transactions
           WHERE user_id = ?
             AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now', 'localtime')""",
        (user_id,)
    ).fetchone()
    conn.close()
    return row


# ── Users / reminders ──────────────────────────────────────────────────────

def save_user(user_id: int, chat_id: int):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, chat_id) VALUES (?, ?)",
        (user_id, chat_id)
    )
    conn.execute("UPDATE users SET chat_id = ? WHERE user_id = ?", (chat_id, user_id))
    conn.commit()
    conn.close()


def set_reminder(user_id: int, hour: int, minute: int):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET remind_hour = ?, remind_minute = ? WHERE user_id = ?",
        (hour, minute, user_id)
    )
    conn.commit()
    conn.close()


def get_reminder(user_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT remind_hour, remind_minute FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row


def get_all_reminder_users(hour: int, minute: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT chat_id, user_id FROM users WHERE remind_hour = ? AND remind_minute = ?",
        (hour, minute)
    ).fetchall()
    conn.close()
    return rows


# ── Limits ─────────────────────────────────────────────────────────────────

def set_limit(user_id: int, category: str, monthly_limit: float):
    conn = get_conn()
    conn.execute(
        """INSERT INTO limits (user_id, category, monthly_limit) VALUES (?, ?, ?)
           ON CONFLICT(user_id, category) DO UPDATE SET monthly_limit = excluded.monthly_limit""",
        (user_id, category, monthly_limit)
    )
    conn.commit()
    conn.close()


def get_limits(user_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, category, monthly_limit FROM limits WHERE user_id = ? ORDER BY category",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def delete_limit(limit_id: int, user_id: int) -> bool:
    conn = get_conn()
    result = conn.execute(
        "DELETE FROM limits WHERE id = ? AND user_id = ?", (limit_id, user_id)
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0
