# session/session_store.py

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("./data/sessions.db")


class SessionStore:
    """SQLite 会话持久化存储"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title      TEXT,
                    status     TEXT DEFAULT 'active',
                    created_at TEXT,
                    updated_at TEXT,
                    metadata   TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS task_results (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    trace_id   TEXT NOT NULL,
                    agent_id   TEXT NOT NULL,
                    result     TEXT,
                    status     TEXT,
                    created_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
            """)
        logger.info("✅ Session 数据库已就绪")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_session(self, session_id: str, title: str = "", metadata: dict = {}):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions
                (session_id, title, status, created_at, updated_at, metadata)
                VALUES (?, ?, 'active', ?, ?, ?)
            """,
                (session_id, title, now, now, json.dumps(metadata, ensure_ascii=False)),
            )

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, status: str = None) -> List[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE status=? ORDER BY updated_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def close_session(self, session_id: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET status='closed', updated_at=? WHERE session_id=?",
                (datetime.now().isoformat(), session_id),
            )

    def append_message(self, session_id: str, role: str, content: str):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (session_id, role, content, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at=? WHERE session_id=?", (now, session_id)
            )

    def get_messages(self, session_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def save_result(
        self,
        session_id: str,
        trace_id: str,
        agent_id: str,
        result: any,
        status: str = "success",
    ):
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO task_results
                (session_id, trace_id, agent_id, result, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    trace_id,
                    agent_id,
                    json.dumps(result, ensure_ascii=False, default=str),
                    status,
                    datetime.now().isoformat(),
                ),
            )

    def get_results(self, session_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM task_results WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]
