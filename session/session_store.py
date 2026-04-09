# session/session_store.py
"""
Session 持久化存储

可靠性特性:
- 事务写入 (BEGIN/COMMIT)
- 索引: session_id, updated_at, task_id
- Token 预算截断
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("./data/sessions.db")

MAX_TOKENS_BUDGET = 4096


def estimate_tokens(text: str) -> int:
    """简单估算 token 数量（中英文混合）"""
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    english_words = len(text) - chinese_chars
    return chinese_chars * 2 + english_words // 4


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
                    token_count INTEGER DEFAULT 0,
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

                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                    ON sessions(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                    ON messages(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_task_results_session_id
                    ON task_results(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_task_results_trace_id
                    ON task_results(trace_id);
            """)
        logger.info("✅ Session 数据库已就绪 (with indexes)")

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

    def list_sessions(self, status: str = None, limit: int = 50) -> List[dict]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    """SELECT * FROM sessions WHERE status=?
                       ORDER BY updated_at DESC LIMIT ?""",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM sessions
                       ORDER BY updated_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def close_session(self, session_id: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET status='closed', updated_at=? WHERE session_id=?",
                (datetime.now().isoformat(), session_id),
            )

    def append_message(self, session_id: str, role: str, content: str):
        """追加消息（带事务）"""
        now = datetime.now().isoformat()
        token_count = estimate_tokens(content)
        with self._conn() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")
                conn.execute(
                    """
                    INSERT INTO messages (session_id, role, content, created_at, token_count)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (session_id, role, content, now, token_count),
                )
                conn.execute(
                    "UPDATE sessions SET updated_at=? WHERE session_id=?",
                    (now, session_id),
                )
                conn.commit()
            except Exception as e:
                conn.execute("ROLLBACK")
                raise e

    def truncate_messages_by_token_budget(
        self, session_id: str, max_tokens: int = MAX_TOKENS_BUDGET
    ) -> int:
        """
        按 token 预算截断消息历史

        保留最新的消息，确保总 token 数不超过预算
        返回被删除的消息数量
        """
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, role, content, token_count FROM messages
                   WHERE session_id=? ORDER BY id ASC""",
                (session_id,),
            ).fetchall()

            if not rows:
                return 0

            total_tokens = sum(r["token_count"] for r in rows)
            if total_tokens <= max_tokens:
                return 0

            kept_tokens = 0
            kept_ids = []
            deleted_count = 0

            for row in reversed(rows):
                if kept_tokens + row["token_count"] <= max_tokens:
                    kept_tokens += row["token_count"]
                    kept_ids.append(row["id"])
                else:
                    conn.execute("DELETE FROM messages WHERE id=?", (row["id"],))
                    deleted_count += 1

            return deleted_count

    def get_messages(self, session_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT role, content, token_count FROM messages
                   WHERE session_id=? ORDER BY id""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_total_tokens(self, session_id: str) -> int:
        """获取会话总 token 数"""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT SUM(token_count) as total FROM messages
                   WHERE session_id=?""",
                (session_id,),
            ).fetchone()
        return row["total"] if row and row["total"] else 0

    def save_result(
        self,
        session_id: str,
        trace_id: str,
        agent_id: str,
        result: any,
        status: str = "success",
    ):
        """保存任务结果（带事务）"""
        with self._conn() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")
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
                conn.execute(
                    "UPDATE sessions SET updated_at=? WHERE session_id=?",
                    (datetime.now().isoformat(), session_id),
                )
                conn.commit()
            except Exception as e:
                conn.execute("ROLLBACK")
                raise e

    def get_results(self, session_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM task_results
                   WHERE session_id=? ORDER BY created_at""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_results_by_trace(self, trace_id: str) -> list[dict]:
        """按 trace_id 查询任务结果"""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM task_results
                   WHERE trace_id=? ORDER BY created_at""",
                (trace_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str):
        """删除会话及其关联数据（带事务）"""
        with self._conn() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")
                conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
                conn.execute(
                    "DELETE FROM task_results WHERE session_id=?", (session_id,)
                )
                conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
                conn.commit()
            except Exception as e:
                conn.execute("ROLLBACK")
                raise e

    def get_message_count(self, session_id: str) -> int:
        """获取会话消息数量"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return row["cnt"] if row else 0
