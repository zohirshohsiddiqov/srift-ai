import sqlite3

DB_NAME = "bot_data.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Foydalanuvchilar jadvali
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            is_blocked INTEGER DEFAULT 0
        )
    """
    )

    # Sozlamalar jadvali (Kanal username'ini saqlash uchun)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """
    )

    conn.commit()
    conn.close()


def add_user(user_id: int, full_name: str, username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (user_id, full_name, username, is_blocked)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name=excluded.full_name,
            username=excluded.username
    """,
        (user_id, full_name, username),
    )
    conn.commit()
    conn.close()


def is_user_blocked(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT is_blocked FROM users WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return bool(row and row[0] == 1)


def block_user(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def unblock_user(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,)
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
    blocked_users = cursor.fetchone()[0]

    conn.close()
    return total_users, blocked_users


def get_all_active_user_ids():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_blocked = 0")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


# KANAL SOZLAMALARI UCHUN FUNKSIYALAR
def set_required_channel(channel_username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO settings (key, value)
        VALUES ('required_channel', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """,
        (channel_username,),
    )
    conn.commit()
    conn.close()


def get_required_channel() -> str:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM settings WHERE key = 'required_channel'"
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""
