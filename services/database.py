"""
Database Service Module
版本: rev3
SQLite 資料庫連線與操作

功能:
- 初始化資料庫與資料表
- 提供連線管理
- 基礎 CRUD 操作
"""

import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from config import config


class DatabaseService:
    """SQLite 資料庫服務"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._ensure_directory()
        self._init_database()
    
    def _ensure_directory(self):
        """確保資料庫目錄存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def _init_database(self):
        """初始化資料庫，建立必要的資料表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 建立對話訊息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'model')),
                    message_type TEXT DEFAULT 'text',
                    message_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 建立索引加速查詢
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_chat_user_id 
                ON chat_messages(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_chat_created_at 
                ON chat_messages(created_at)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_chat_user_created 
                ON chat_messages(user_id, created_at)
            ''')
            
            conn.commit()
            print(f"[Database] Initialized: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """取得資料庫連線 (使用 context manager 自動管理)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 讓結果可以用欄位名稱存取
        try:
            yield conn
        finally:
            conn.close()
    
    def execute(self, query: str, params: tuple = ()) -> list:
        """執行查詢並回傳結果"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """執行插入並回傳 last row id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid
    
    def get_db_stats(self) -> dict:
        """取得資料庫統計資訊"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 總訊息數
            cursor.execute("SELECT COUNT(*) as count FROM chat_messages")
            total_messages = cursor.fetchone()['count']
            
            # 使用者數
            cursor.execute("SELECT COUNT(DISTINCT user_id) as count FROM chat_messages")
            total_users = cursor.fetchone()['count']
            
            # 最近訊息時間
            cursor.execute("SELECT MAX(created_at) as latest FROM chat_messages")
            latest = cursor.fetchone()['latest']
            
            # 資料庫檔案大小
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                "total_messages": total_messages,
                "total_users": total_users,
                "latest_message": latest,
                "database_size_bytes": db_size,
                "database_path": self.db_path
            }


# 建立全域資料庫實例
db_service = DatabaseService()
