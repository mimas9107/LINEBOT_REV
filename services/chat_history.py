"""
Chat History Service Module
版本: rev2.4.5
對話歷史記錄功能 (使用 SQLite)

更新紀錄:
- rev2.2: 從 feature2 導入 SQLite 對話歷史核心
"""

from datetime import datetime
from typing import Optional

from config import config
from .database import db_service


class ChatHistoryService:
    """對話歷史服務"""

    def __init__(self):
        self.db = db_service
        self.default_history_limit = config.CHAT_HISTORY_LENGTH

    def save_user_message(
        self,
        user_id: str,
        message_text: str,
        message_type: str = "text",
    ) -> int:
        """儲存使用者訊息"""
        query = """
            INSERT INTO chat_messages (user_id, role, message_type, message_text)
            VALUES (?, 'user', ?, ?)
        """
        record_id = self.db.execute_insert(query, (user_id, message_type, message_text))
        print(f"[ChatHistory] Saved user message: {record_id}")
        return record_id

    def save_model_response(
        self,
        user_id: str,
        message_text: str,
        message_type: str = "text",
    ) -> int:
        """儲存 AI 回應"""
        query = """
            INSERT INTO chat_messages (user_id, role, message_type, message_text)
            VALUES (?, 'model', ?, ?)
        """
        record_id = self.db.execute_insert(query, (user_id, message_type, message_text))
        print(f"[ChatHistory] Saved model response: {record_id}")
        return record_id

    def get_chat_history(self, user_id: str, limit: Optional[int] = None) -> list[dict]:
        """取得使用者的對話歷史，按時間正序排列"""
        if limit is None:
            limit = self.default_history_limit

        query = """
            SELECT role, message_text, message_type, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        results = self.db.execute(query, (user_id, limit))
        results.reverse()

        return [
            {
                "userId": user_id if row["role"] == "user" else "model",
                "role": row["role"],
                "messageText": row["message_text"],
                "messageType": row["message_type"],
                "createdAt": row["created_at"],
            }
            for row in results
        ]

    def get_all_messages(self, limit: int = 1000, offset: int = 0) -> list[dict]:
        """取得所有對話訊息"""
        query = """
            SELECT id, user_id, role, message_type, message_text, created_at
            FROM chat_messages
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        return self.db.execute(query, (limit, offset))

    def get_user_messages(self, user_id: str, limit: int = 100) -> list[dict]:
        """取得特定使用者的所有訊息"""
        query = """
            SELECT id, role, message_type, message_text, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        return self.db.execute(query, (user_id, limit))

    def get_unique_users(self) -> list[dict]:
        """取得所有不重複的使用者 ID 與訊息統計"""
        query = """
            SELECT
                user_id,
                COUNT(*) as message_count,
                MIN(created_at) as first_message,
                MAX(created_at) as last_message
            FROM chat_messages
            GROUP BY user_id
            ORDER BY last_message DESC
        """
        return self.db.execute(query)

    def delete_user_history(self, user_id: str) -> int:
        """刪除特定使用者的所有對話記錄"""
        return self.db.execute_write(
            "DELETE FROM chat_messages WHERE user_id = ?",
            (user_id,),
        )

    def export_to_dict(self) -> dict:
        """匯出整個資料庫為字典格式"""
        return {
            "export_time": datetime.now().isoformat(),
            "stats": self.db.get_db_stats(),
            "users": self.get_unique_users(),
            "messages": self.get_all_messages(limit=10000),
        }


chat_history_service = ChatHistoryService()


def save_user_message(
    user_id: str,
    message_text: str,
    message_type: str = "text",
) -> int:
    """儲存使用者訊息"""
    return chat_history_service.save_user_message(user_id, message_text, message_type)


def save_model_response(
    user_id: str,
    message_text: str,
    message_type: str = "text",
) -> int:
    """儲存 AI 回應"""
    return chat_history_service.save_model_response(user_id, message_text, message_type)


def get_chat_history(user_id: str, limit: Optional[int] = None) -> list[dict]:
    """取得對話歷史"""
    return chat_history_service.get_chat_history(user_id, limit)
