"""
Database Service Module
版本: rev3.1
SQLite 資料庫連線與操作

更新紀錄:
- rev3.1: 新增 maintenance mode、restore 功能、rollback 機制
- rev3: 初始版本
"""

import sqlite3
import os
import shutil
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from config import config


class DatabaseMaintenanceError(Exception):
    """資料庫維護中例外"""
    pass


class DatabaseRestoreError(Exception):
    """資料庫還原失敗例外"""
    pass


class DatabaseService:
    """SQLite 資料庫服務（支援 maintenance mode 與 restore）"""
    
    # SQLite 檔案標頭（前 16 bytes）
    SQLITE_HEADER = b'SQLite format 3\x00'
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._maintenance_mode = False
        self._maintenance_reason = ""
        self._lock = threading.RLock()  # 可重入鎖
        
        self._ensure_directory()
        self._init_database()
    
    # ===== Maintenance Mode 管理 =====
    
    @property
    def is_maintenance(self) -> bool:
        """是否處於維護模式"""
        return self._maintenance_mode
    
    @property
    def maintenance_reason(self) -> str:
        """維護原因"""
        return self._maintenance_reason
    
    def set_maintenance(self, enabled: bool, reason: str = ""):
        """
        設定維護模式
        
        Args:
            enabled: 是否啟用
            reason: 維護原因
        """
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
    
    # ===== 基本初始化 =====
    
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
            
            # 建立索引
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
    
    # ===== 連線管理 =====
    
    @contextmanager
    def get_connection(self):
        """取得資料庫連線（使用 context manager 自動管理）"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # ===== CRUD 操作 =====
    
    def execute(self, query: str, params: tuple = ()) -> list:
        """執行查詢並回傳結果"""
        # 讀取操作在維護模式下仍可執行
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """執行插入並回傳 last row id"""
        self._check_maintenance()  # 寫入操作需檢查維護模式
        
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.lastrowid
    
    # ===== Restore 功能 =====
    
    @staticmethod
    def validate_sqlite_file(file_path: str) -> bool:
        """
        驗證檔案是否為有效的 SQLite 資料庫
        
        Args:
            file_path: 檔案路徑
        
        Returns:
            是否為有效的 SQLite 檔案
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
                return header == DatabaseService.SQLITE_HEADER
        except Exception as e:
            print(f"[Database] SQLite validation failed: {e}")
            return False
    
    @staticmethod
    def validate_sqlite_integrity(file_path: str) -> tuple[bool, str]:
        """
        驗證 SQLite 資料庫完整性
        
        Args:
            file_path: 檔案路徑
        
        Returns:
            (是否有效, 錯誤訊息)
        """
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # 檢查完整性
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            
            if result != 'ok':
                conn.close()
                return False, f"Integrity check failed: {result}"
            
            # 檢查必要的資料表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='chat_messages'
            """)
            if not cursor.fetchone():
                conn.close()
                return False, "Missing required table: chat_messages"
            
            # 檢查資料表結構
            cursor.execute("PRAGMA table_info(chat_messages)")
            columns = {row[1] for row in cursor.fetchall()}
            required_columns = {'id', 'user_id', 'role', 'message_text', 'created_at'}
            
            missing = required_columns - columns
            if missing:
                conn.close()
                return False, f"Missing columns: {missing}"
            
            conn.close()
            return True, "OK"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def restore_from_file(self, uploaded_file_path: str, wait_seconds: int = 2) -> dict:
        """
        從上傳的檔案還原資料庫
        
        流程：
        1. 設定 maintenance mode
        2. 等待現有請求完成
        3. 驗證上傳的檔案
        4. 備份現有資料庫
        5. 原子替換
        6. WAL checkpoint + VACUUM
        7. 解除 maintenance mode
        
        Args:
            uploaded_file_path: 上傳的 SQLite 檔案路徑
            wait_seconds: 等待現有請求完成的秒數
        
        Returns:
            還原結果資訊
        """
        backup_path = None
        restore_start = datetime.now()
        
        try:
            # Step 1: 設定 maintenance mode
            self.set_maintenance(True, "Database restore in progress")
            
            # Step 2: 等待現有請求完成
            print(f"[Database] Waiting {wait_seconds}s for pending requests...")
            time.sleep(wait_seconds)
            
            # Step 3: 驗證上傳的檔案
            print("[Database] Validating uploaded file...")
            
            # 3.1 檢查 SQLite header
            if not self.validate_sqlite_file(uploaded_file_path):
                raise DatabaseRestoreError("Invalid SQLite file: header mismatch")
            
            # 3.2 檢查資料庫完整性
            is_valid, error_msg = self.validate_sqlite_integrity(uploaded_file_path)
            if not is_valid:
                raise DatabaseRestoreError(f"Invalid SQLite file: {error_msg}")
            
            print("[Database] Validation passed")
            
            # 取得上傳檔案的統計資訊
            temp_conn = sqlite3.connect(uploaded_file_path)
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("SELECT COUNT(*) FROM chat_messages")
            uploaded_msg_count = temp_cursor.fetchone()[0]
            temp_conn.close()
            
            with self._lock:
                # Step 4: 備份現有資料庫
                if os.path.exists(self.db_path):
                    backup_path = f"{self.db_path}.backup.{int(time.time())}"
                    print(f"[Database] Creating backup: {backup_path}")
                    shutil.copy2(self.db_path, backup_path)
                
                # Step 5: 替換資料庫檔案（處理跨檔案系統情況）
                print("[Database] Replacing database file...")
                
                # os.replace() 無法跨檔案系統，改用 shutil.move()
                # shutil.move() 會自動處理跨檔案系統的情況（先複製再刪除）
                shutil.move(uploaded_file_path, self.db_path)
                
                # Step 6: WAL checkpoint + VACUUM
                print("[Database] Running WAL checkpoint and VACUUM...")
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # WAL checkpoint（如果使用 WAL 模式）
                    try:
                        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    except:
                        pass  # 可能沒有使用 WAL 模式
                    
                    # VACUUM 優化資料庫
                    cursor.execute("VACUUM")
                    
                    # 取得最終統計
                    cursor.execute("SELECT COUNT(*) FROM chat_messages")
                    final_msg_count = cursor.fetchone()[0]
                    
                    conn.commit()
            
            # Step 7: 解除 maintenance mode
            self.set_maintenance(False)
            
            restore_end = datetime.now()
            duration = (restore_end - restore_start).total_seconds()
            
            result = {
                "success": True,
                "message": "Database restored successfully",
                "uploaded_messages": uploaded_msg_count,
                "final_messages": final_msg_count,
                "backup_path": backup_path,
                "duration_seconds": round(duration, 2),
                "restored_at": restore_end.isoformat()
            }
            
            print(f"[Database] Restore completed: {result}")
            return result
            
        except Exception as e:
            print(f"[Database] Restore failed: {e}")
            
            # Rollback: 還原備份
            if backup_path and os.path.exists(backup_path):
                print(f"[Database] Rolling back from backup: {backup_path}")
                try:
                    os.replace(backup_path, self.db_path)
                    print("[Database] Rollback successful")
                except Exception as rollback_error:
                    print(f"[Database] Rollback failed: {rollback_error}")
            
            # 確保解除 maintenance mode
            self.set_maintenance(False)
            
            raise DatabaseRestoreError(f"Restore failed: {str(e)}")
    
    def cleanup_old_backups(self, keep_count: int = 3):
        """
        清理舊的備份檔案，只保留最近 N 個
        
        Args:
            keep_count: 保留的備份數量
        """
        db_dir = os.path.dirname(self.db_path) or '.'
        db_name = os.path.basename(self.db_path)
        
        # 找出所有備份檔案
        backups = []
        for f in os.listdir(db_dir):
            if f.startswith(db_name + '.backup.'):
                full_path = os.path.join(db_dir, f)
                backups.append((full_path, os.path.getmtime(full_path)))
        
        # 按時間排序，刪除舊的
        backups.sort(key=lambda x: x[1], reverse=True)
        
        for backup_path, _ in backups[keep_count:]:
            try:
                os.remove(backup_path)
                print(f"[Database] Removed old backup: {backup_path}")
            except Exception as e:
                print(f"[Database] Failed to remove backup {backup_path}: {e}")
    
    # ===== 統計資訊 =====
    
    def get_db_stats(self) -> dict:
        """取得資料庫統計資訊"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as count FROM chat_messages")
            total_messages = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(DISTINCT user_id) as count FROM chat_messages")
            total_users = cursor.fetchone()['count']
            
            cursor.execute("SELECT MAX(created_at) as latest FROM chat_messages")
            latest = cursor.fetchone()['latest']
            
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                "total_messages": total_messages,
                "total_users": total_users,
                "latest_message": latest,
                "database_size_bytes": db_size,
                "database_path": self.db_path,
                "maintenance_mode": self._maintenance_mode,
                "maintenance_reason": self._maintenance_reason
            }


# 建立全域資料庫實例
db_service = DatabaseService()
