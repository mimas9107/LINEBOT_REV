"""
Bookmark Service Module
版本: rev2
處理書籤功能與 Google Apps Script 互動
"""

import json
import time
import requests
from config import config


class BookmarkService:
    """書籤與歷史訊息服務"""
    
    def __init__(self):
        self.gas_url = config.GOOGLE_APPS_SCRIPT_URL
    
    def _is_configured(self) -> bool:
        """檢查 Google Apps Script URL 是否已設定"""
        return bool(self.gas_url)
    
    def get_chat_history(self, user_id: str, limit: int = None) -> list[dict]:
        """
        從 Google Sheet 取得使用者的歷史對話
        
        Args:
            user_id: LINE 使用者 ID
            limit: 取得的訊息數量上限
        
        Returns:
            歷史對話列表，格式為 [{"userId": "...", "messageText": "..."}]
        """
        if not self._is_configured():
            print("[BookmarkService] GOOGLE_APPS_SCRIPT_URL not set")
            return []
        
        if limit is None:
            limit = config.CHAT_HISTORY_LENGTH
        
        payload = {
            "action": "get_history",
            "userId": user_id,
            "limit": limit
        }
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = requests.post(
                self.gas_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            print(f"[BookmarkService] get_history response: {response.content}")
            response.raise_for_status()
            
            history_data = response.json().get("history", [])
            print(f"[BookmarkService] history_data: {history_data}")
            return history_data
            
        except requests.exceptions.RequestException as e:
            print(f"[BookmarkService] Error fetching chat history: {e}")
            return []
    
    def save_message(self, timestamp: int, user_id: str, message_type: str, message_text: str) -> bool:
        """
        將訊息儲存到 Google Sheet
        
        Args:
            timestamp: 訊息時間戳記
            user_id: 使用者 ID
            message_type: 訊息類型 (text, image, etc.)
            message_text: 訊息內容
        
        Returns:
            是否儲存成功
        """
        if not self._is_configured():
            print("[BookmarkService] GOOGLE_APPS_SCRIPT_URL not set")
            return False
        
        payload = {
            "timestamp": timestamp,
            "userId": user_id,
            "messageType": message_type,
            "messageText": message_text
        }
        headers = {'Content-Type': 'application/json'}
        
        try:
            # 加入小延遲，防止訊息傳入太快 Google Apps Script 來不及寫入
            time.sleep(0.25)
            
            response = requests.post(
                self.gas_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status()
            print(f"[BookmarkService] Message saved. Status: {response.status_code}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"[BookmarkService] Error saving message: {e}")
            return False
    
    def log_keepalive(self, function_name: str, status: str = "OK", note: str = "") -> bool:
        """
        記錄保持清醒的 log 到 Google Sheet
        
        Args:
            function_name: 執行的函式名稱
            status: 狀態
            note: 備註
        
        Returns:
            是否記錄成功
        """
        if not self._is_configured():
            print("[BookmarkService] GOOGLE_APPS_SCRIPT_URL not set")
            return False
        
        from datetime import datetime
        
        payload = {
            "action": "stay_awake_log",
            "timestamp": datetime.now().isoformat(),
            "functionName": function_name,
            "status": status,
            "note": note
        }
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = requests.post(
                self.gas_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            print(f"[BookmarkService] Keepalive logged. Status: {response.status_code}")
            return True
            
        except Exception as e:
            print(f"[BookmarkService] Error logging keepalive: {e}")
            return False


# 建立全域服務實例
bookmark_service = BookmarkService()


def get_chat_history(user_id: str, limit: int = None) -> list[dict]:
    """便捷函式：取得聊天歷史"""
    return bookmark_service.get_chat_history(user_id, limit)


def save_message(timestamp: int, user_id: str, message_type: str, message_text: str) -> bool:
    """便捷函式：儲存訊息"""
    return bookmark_service.save_message(timestamp, user_id, message_type, message_text)


def log_keepalive(function_name: str, status: str = "OK", note: str = "") -> bool:
    """便捷函式：記錄保活 log"""
    return bookmark_service.log_keepalive(function_name, status, note)
