# evolution/approval_queue.py

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("./data/approvals.db")


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    INSTALLED = "installed"


class ApprovalQueue:
    """技能申请审批队列"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id     TEXT NOT NULL,
                    skill_id     TEXT NOT NULL,
                    title        TEXT,
                    reason       TEXT,
                    benefit      TEXT,
                    risk         TEXT,
                    urgency      TEXT DEFAULT 'medium',
                    description  TEXT,
                    instruction  TEXT,
                    status       TEXT DEFAULT 'pending',
                    reviewer     TEXT DEFAULT '',
                    review_note  TEXT DEFAULT '',
                    created_at   TEXT,
                    reviewed_at  TEXT
                )
            """)
        logger.info("✅ 审批队列数据库已就绪")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def submit(self, request: dict) -> int:
        """提交申请单，返回申请 ID"""
        with self._conn() as conn:
            existing = conn.execute(
                """
                SELECT id FROM approvals
                WHERE agent_id=? AND skill_id=? AND status='pending'
            """,
                (request["agent_id"], request["skill_id"]),
            ).fetchone()

            if existing:
                logger.info(f"⚠️ 已有相同 pending 申请: #{existing['id']}")
                return existing["id"]

            cursor = conn.execute(
                """
                INSERT INTO approvals
                (agent_id, skill_id, title, reason, benefit, risk,
                 urgency, description, instruction, status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    request.get("agent_id"),
                    request.get("skill_id"),
                    request.get("title", ""),
                    request.get("reason", ""),
                    request.get("benefit", ""),
                    request.get("risk", ""),
                    request.get("urgency", "medium"),
                    request.get("description", ""),
                    request.get("instruction", ""),
                    ApprovalStatus.PENDING,
                    datetime.now().isoformat(),
                ),
            )
            approval_id = cursor.lastrowid

        logger.info(
            f"📬 申请已提交: #{approval_id} [{request['agent_id']}] → [{request['skill_id']}]"
        )
        return approval_id

    def approve(self, approval_id: int, reviewer: str = "admin", note: str = ""):
        self._update_status(approval_id, ApprovalStatus.APPROVED, reviewer, note)
        logger.info(f"✅ 申请 #{approval_id} 已批准 by {reviewer}")

    def reject(self, approval_id: int, reviewer: str = "admin", note: str = ""):
        self._update_status(approval_id, ApprovalStatus.REJECTED, reviewer, note)
        logger.info(f"❌ 申请 #{approval_id} 已拒绝 by {reviewer}")

    def mark_installed(self, approval_id: int):
        self._update_status(approval_id, ApprovalStatus.INSTALLED)
        logger.info(f"📦 申请 #{approval_id} 已安装")

    def _update_status(
        self,
        approval_id: int,
        status: ApprovalStatus,
        reviewer: str = "",
        note: str = "",
    ):
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE approvals
                SET status=?, reviewer=?, review_note=?, reviewed_at=?
                WHERE id=?
            """,
                (status, reviewer, note, datetime.now().isoformat(), approval_id),
            )

    def list_pending(self) -> list[dict]:
        return self._query_by_status(ApprovalStatus.PENDING)

    def list_approved(self) -> List[dict]:
        return self._query_by_status(ApprovalStatus.APPROVED)

    def list_all(self) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM approvals ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def get(self, approval_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE id=?", (approval_id,)
            ).fetchone()
        return dict(row) if row else None

    def _query_by_status(self, status: ApprovalStatus) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status=? ORDER BY id DESC", (status,)
            ).fetchall()
        return [dict(r) for r in rows]

    def pending_count(self) -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM approvals WHERE status='pending'"
            ).fetchone()[0]
