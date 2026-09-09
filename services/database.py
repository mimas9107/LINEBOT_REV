"""
Database Service Module
版本: rev2.4.3
SQLite 資料庫連線與操作

更新紀錄:
- rev2.2: 從 feature2 導入 SQLite 對話資料庫核心；不包含上傳還原流程
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Optional

from config import config


class DatabaseMaintenanceError(Exception):
    """資料庫維護中例外"""


class DatabaseService:
    """SQLite 資料庫服務"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._maintenance_mode = False
        self._maintenance_reason = ""
        self._lock = threading.RLock()

        self._ensure_directory()
        self._init_database()

    @property
    def is_maintenance(self) -> bool:
        """是否處於維護模式"""
        return self._maintenance_mode

    @property
    def maintenance_reason(self) -> str:
        """維護原因"""
        return self._maintenance_reason

    def set_maintenance(self, enabled: bool, reason: str = ""):
        """設定維護模式"""
        with self._lock:
            self._maintenance_mode = enabled
            self._maintenance_reason = reason if enabled else ""
            status = "ENABLED" if enabled else "DISABLED"
            print(f"[Database] Maintenance mode {status}: {reason}")

    def _check_maintenance(self):
        """檢查是否處於維護模式，若是則拋出例外"""
        if self._maintenance_mode:
            raise DatabaseMaintenanceError(
                f"Database is in maintenance mode: {self._maintenance_reason}"
            )

    def _ensure_directory(self):
        """確保資料庫目錄存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _init_database(self):
        """初始化資料庫，建立必要的資料表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'model')),
                    message_type TEXT DEFAULT 'text',
                    message_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_user_id
                ON chat_messages(user_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_created_at
                ON chat_messages(created_at)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_user_created
                ON chat_messages(user_id, created_at)
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    remind_at TIMESTAMP NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'sent', 'cancelled')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified_at TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_reminders_due
                ON reminders(status, remind_at)
                """
            )
            conn.commit()
            print(f"[Database] Initialized: {self.db_path}")

    @contextmanager
    def get_connection(self):
        """取得資料庫連線"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, query: str, params: tuple = ()) -> list[dict]:
        """執行讀取查詢並回傳結果"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """執行插入並回傳 last row id"""
        self._check_maintenance()
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.lastrowid

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """執行寫入/刪除並回傳受影響列數"""
        self._check_maintenance()
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount

    def get_db_stats(self) -> dict:
        """取得資料庫統計資訊"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as count FROM chat_messages")
            total_messages = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(DISTINCT user_id) as count FROM chat_messages")
            total_users = cursor.fetchone()["count"]

            cursor.execute("SELECT MAX(created_at) as latest FROM chat_messages")
            latest = cursor.fetchone()["latest"]

        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

        return {
            "total_messages": total_messages,
            "total_users": total_users,
            "latest_message": latest,
            "database_size_bytes": db_size,
            "database_path": self.db_path,
            "maintenance_mode": self._maintenance_mode,
            "maintenance_reason": self._maintenance_reason,
        }


db_service = DatabaseService()
