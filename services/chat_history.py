"""
Chat History Service Module
版本: rev3.1
對話歷史記錄功能 (使用 SQLite)

更新紀錄:
- rev3.1: 配合 maintenance mode
- rev3: 初始版本
"""

from datetime import datetime
from typing import Optional
from .database import db_service
from config import config


class ChatHistoryService:
    """對話歷史服務"""
    
    def __init__(self):
        self.db = db_service
        self.default_history_limit = config.CHAT_HISTORY_LENGTH
    
    def save_user_message(
        self,
        user_id: str,
        message_text: str,
        message_type: str = 'text'
    ) -> int:
        """
        儲存使用者訊息
        
        Args:
            user_id: LINE 使用者 ID
            message_text: 訊息內容
            message_type: 訊息類型 (text, image, etc.)
        
        Returns:
            新增的記錄 ID
        """
        query = '''
            INSERT INTO chat_messages (user_id, role, message_type, message_text)
            VALUES (?, 'user', ?, ?)
        '''
        record_id = self.db.execute_insert(query, (user_id, message_type, message_text))
        print(f"[ChatHistory] Saved user message: {record_id}")
        return record_id
    
    def save_model_response(
        self,
        user_id: str,
        message_text: str,
        message_type: str = 'text'
    ) -> int:
        """
        儲存 AI 回應
        
        Args:
            user_id: LINE 使用者 ID (對應的使用者)
            message_text: AI 回應內容
            message_type: 訊息類型
        
        Returns:
            新增的記錄 ID
        """
        query = '''
            INSERT INTO chat_messages (user_id, role, message_type, message_text)
            VALUES (?, 'model', ?, ?)
        '''
        record_id = self.db.execute_insert(query, (user_id, message_type, message_text))
        print(f"[ChatHistory] Saved model response: {record_id}")
        return record_id
    
    def get_chat_history(
        self,
        user_id: str,
        limit: int = None
    ) -> list[dict]:
        """
        取得使用者的對話歷史
        
        Args:
            user_id: LINE 使用者 ID
            limit: 取得的訊息數量上限
        
        Returns:
            對話歷史列表，按時間正序排列
            格式: [{"role": "user/model", "messageText": "..."}]
        """
        if limit is None:
            limit = self.default_history_limit
        
        # 取得最近的訊息（倒序取，然後反轉成正序）
        query = '''
            SELECT role, message_text, message_type, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        '''
        results = self.db.execute(query, (user_id, limit))
        
        # 反轉成時間正序
        results.reverse()
        
        # 轉換成與舊版相容的格式
        history = []
        for row in results:
            history.append({
                "userId": user_id if row['role'] == 'user' else 'model',
                "role": row['role'],
                "messageText": row['message_text'],
                "messageType": row['message_type'],
                "createdAt": row['created_at']
            })
        
        print(f"[ChatHistory] Retrieved {len(history)} messages for user {user_id[:10]}...")
        return history
    
    def get_all_messages(
        self,
        limit: int = 1000,
        offset: int = 0
    ) -> list[dict]:
        """
        取得所有對話訊息 (用於匯出/除錯)
        
        Args:
            limit: 取得數量上限
            offset: 起始位置
        
        Returns:
            所有對話訊息列表
        """
        query = '''
            SELECT id, user_id, role, message_type, message_text, created_at
            FROM chat_messages
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        '''
        return self.db.execute(query, (limit, offset))
    
    def get_user_messages(self, user_id: str, limit: int = 100) -> list[dict]:
        """
        取得特定使用者的所有訊息
        
        Args:
            user_id: 使用者 ID
            limit: 數量上限
        
        Returns:
            該使用者的訊息列表
        """
        query = '''
            SELECT id, role, message_type, message_text, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        '''
        return self.db.execute(query, (user_id, limit))
    
    def get_unique_users(self) -> list[dict]:
        """
        取得所有不重複的使用者 ID 與訊息統計
        
        Returns:
            使用者列表與統計
        """
        query = '''
            SELECT 
                user_id,
                COUNT(*) as message_count,
                MIN(created_at) as first_message,
                MAX(created_at) as last_message
            FROM chat_messages
            GROUP BY user_id
            ORDER BY last_message DESC
        '''
        return self.db.execute(query, ())
    
    def delete_user_history(self, user_id: str) -> int:
        """
        刪除特定使用者的所有對話記錄
        
        Args:
            user_id: 使用者 ID
        
        Returns:
            刪除的記錄數
        """
        # 先計算數量
        count_query = "SELECT COUNT(*) as count FROM chat_messages WHERE user_id = ?"
        result = self.db.execute(count_query, (user_id,))
        count = result[0]['count'] if result else 0
        
        # 執行刪除
        delete_query = "DELETE FROM chat_messages WHERE user_id = ?"
        self.db.execute(delete_query, (user_id,))
        
        print(f"[ChatHistory] Deleted {count} messages for user {user_id[:10]}...")
        return count
    
    def export_to_dict(self) -> dict:
        """
        匯出整個資料庫為字典格式
        
        Returns:
            包含所有資料的字典
        """
        stats = self.db.get_db_stats()
        messages = self.get_all_messages(limit=10000)
        users = self.get_unique_users()
        
        return {
            "export_time": datetime.now().isoformat(),
            "stats": stats,
            "users": users,
            "messages": messages
        }


# 建立全域服務實例
chat_history_service = ChatHistoryService()


# 便捷函式
def save_user_message(user_id: str, message_text: str, message_type: str = 'text') -> int:
    """儲存使用者訊息"""
    return chat_history_service.save_user_message(user_id, message_text, message_type)


def save_model_response(user_id: str, message_text: str, message_type: str = 'text') -> int:
    """儲存 AI 回應"""
    return chat_history_service.save_model_response(user_id, message_text, message_type)


def get_chat_history(user_id: str, limit: int = None) -> list[dict]:
    """取得對話歷史"""
    return chat_history_service.get_chat_history(user_id, limit)
