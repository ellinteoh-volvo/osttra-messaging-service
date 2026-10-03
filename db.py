import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "messages.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = sqlite3.connect(DB_PATH)

    try:
        # Database constraints provide a final layer of data-integrity protection in addition to API validation.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient TEXT NOT NULL CHECK (trim(recipient) <> ''),
                text TEXT NOT NULL CHECK (trim(text) <> ''),
                unread INTEGER NOT NULL DEFAULT 1 CHECK (unread IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Most reads filter by recipient and sort chronologically, so this index supports that access pattern.
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_recipient_created
            ON messages (recipient, created_at, id)
        """)

        connection.commit()

    finally:
        connection.close()


if __name__ == "__main__":
    init_db()
    print("Database created successfully!")