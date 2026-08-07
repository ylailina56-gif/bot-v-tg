import os
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def query(sql, params=(), fetch=None):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        if fetch == "one":
            data = cur.fetchone()
        elif fetch == "all":
            data = cur.fetchall()
        else:
            data = None
        conn.commit()
        return data
    finally:
        conn.close()


def init_db():
    query("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense', 'saving')),
            amount DOUBLE PRECISION NOT NULL,
            category TEXT NOT NULL,
            note TEXT,
            created_at TEXT
        )
    """)
    query("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            remind_hour INTEGER,
            remind_minute INTEGER
        )
    """)
    query("""
        CREATE TABLE IF NOT EXISTS limits (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            category TEXT NOT NULL,
            monthly_limit DOUBLE PRECISION NOT NULL,
            UNIQUE(user_id, category)
        )
    """)


def add_transaction(user_id, ttype, amount, category, note=""):
    query(
        "INSERT INTO transactions (user_id, type, amount, category, note, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (user_id, ttype, amount, category, note,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )


def get_balance(user_id):
    row = query(
        """
        SELECT
          COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) -
          COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS balance
        FROM transactions WHERE user_id = %s
        """,
        (user_id,),
        fetch="one",
    )
    return float(row["balance"]) if row else 0.0


def get_history(user_id, limit=10):
    return query(
        "SELECT id, type, amount, category, note, created_at "
        "FROM transactions WHERE user_id = %s ORDER BY id DESC LIMIT %s",
        (user_id, limit),
        fetch="all",
    ) or []


def get_categories_summary(user_id, ttype):
    return query(
        "SELECT category, SUM(amount) AS total "
        "FROM transactions WHERE user_id = %s AND type = %s "
        "GROUP BY category ORDER BY total DESC",
        (user_id, ttype),
        fetch="all",
    ) or []


def delete_last(user_id):
    row = query(
        "SELECT id FROM transactions WHERE user_id = %s ORDER BY id DESC LIMIT 1",
        (user_id,),
        fetch="one",
    )
    if not row:
        return False
    query("DELETE FROM transactions WHERE id = %s", (row["id"],))
    return True


def get_monthly_summary(user_id):
    prefix = datetime.now().strftime("%Y-%m")
    row = query(
        """
        SELECT
          COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END), 0) AS income,
          COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS expense
        FROM transactions
        WHERE user_id = %s AND created_at LIKE %s
        """,
        (user_id, prefix + "%"),
        fetch="one",
    )
    if not row:
        return None
    return {"income": float(row["income"]), "expense": float(row["expense"])}


def save_user(user_id, chat_id):
    query(
        "INSERT INTO users (user_id, chat_id) VALUES (%s, %s) "
        "ON CONFLICT (user_id) DO UPDATE SET chat_id = EXCLUDED.chat_id",
        (user_id, chat_id),
    )


def set_reminder(user_id, hour, minute):
    query(
        "UPDATE users SET remind_hour = %s, remind_minute = %s WHERE user_id = %s",
        (hour, minute, user_id),
    )


def get_reminder(user_id):
    return query(
        "SELECT remind_hour, remind_minute FROM users WHERE user_id = %s",
        (user_id,),
        fetch="one",
    )


def get_all_reminder_users(hour, minute):
    return query(
        "SELECT chat_id, user_id FROM users WHERE remind_hour = %s AND remind_minute = %s",
        (hour, minute),
        fetch="all",
    ) or []


def set_limit(user_id, category, monthly_limit):
    query(
        "INSERT INTO limits (user_id, category, monthly_limit) VALUES (%s, %s, %s) "
        "ON CONFLICT (user_id, category) DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit",
        (user_id, category, monthly_limit),
    )
