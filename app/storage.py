import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class StorageUnavailableError(Exception):
    pass


class LeadStorage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init_db(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS leads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        name TEXT NOT NULL,
                        contact TEXT NOT NULL,
                        source TEXT NOT NULL,
                        comment TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise StorageUnavailableError(str(exc)) from exc

    def save_lead(self, lead: dict) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO leads(created_at, name, contact, source, comment)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        created_at,
                        lead["name"],
                        lead["contact"],
                        lead["source"],
                        lead["comment"],
                    ),
                )
                conn.commit()
                lead_id = int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise StorageUnavailableError(str(exc)) from exc

        return lead_id
