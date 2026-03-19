"""SQLite 记忆存储层"""

import sqlite3
from pathlib import Path
from typing import Any, Optional


class SQLiteStore:
    def __init__(self, db_path: Path, max_size_mb: int = 100):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_size_mb = max_size_mb
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens INTEGER DEFAULT 0,
                tool_name TEXT,
                tool_call_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                original_count INTEGER DEFAULT 0,
                summary_type TEXT DEFAULT 'auto',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 5,
                tags TEXT,
                user_id TEXT,
                agent_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence INTEGER DEFAULT 5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, agent_id, key)
            )
        """)

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session "
            "ON messages(session_id, created_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_user " "ON events(user_id, agent_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_type " "ON events(event_type)"
        )

        conn.commit()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
    ) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages
            (session_id, role, content, tokens, tool_name, tool_call_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, content, tokens, tool_name, tool_call_id),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? "
            "ORDER BY created_at ASC LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_message_count(self, session_id: str) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            (session_id,),
        )
        return cursor.fetchone()[0]

    def add_summary(
        self,
        session_id: str,
        summary: str,
        original_count: int,
        summary_type: str = "auto",
    ) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO summaries "
            "(session_id, summary, original_count, summary_type) "
            "VALUES (?, ?, ?, ?)",
            (session_id, summary, original_count, summary_type),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def get_latest_summary(
        self,
        session_id: str,
    ) -> Optional[dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM summaries WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_summaries(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM summaries WHERE session_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def add_event(
        self,
        event_type: str,
        content: str,
        importance: int = 5,
        tags: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events "
            "(event_type, content, importance, tags, user_id, agent_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_type, content, importance, tags, user_id, agent_id),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def get_events(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def set_profile(
        self,
        user_id: str,
        agent_id: str,
        key: str,
        value: str,
        confidence: int = 5,
    ) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_profile (user_id, agent_id, key, value, confidence)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, agent_id, key)
            DO UPDATE SET value = excluded.value,
                          confidence = excluded.confidence,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, agent_id, key, value, confidence),
        )
        conn.commit()

    def get_profile(self, user_id: str, agent_id: str) -> dict[str, str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT key, value FROM user_profile " "WHERE user_id = ? AND agent_id = ?",
            (user_id, agent_id),
        )
        return {row["key"]: row["value"] for row in cursor.fetchall()}

    def vacuum_if_needed(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT page_count * page_size as size "
            "FROM pragma_page_count(), pragma_page_size()"
        )
        size_mb = cursor.fetchone()[0] / (1024 * 1024)
        if size_mb > self.max_size_mb:
            cursor.execute("VACUUM")
            conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
