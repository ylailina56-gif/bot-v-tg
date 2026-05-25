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
