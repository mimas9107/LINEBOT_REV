"""
Services Package
版本: rev2.4.2
提供各項服務功能

更新紀錄:
- rev2.2: 新增 SQLite database 與 chat history 服務匯出，不改動既有 Google Sheet history 入口
- rev2: AI 模組改用 google-genai SDK
"""

from .ai_text import chat_with_ai, ai_text_service
from .ai_image import analyze_image, ai_image_service
from .bookmark import (
    get_chat_history,
    save_message,
    log_keepalive,
    bookmark_service
)
from .database import db_service, DatabaseMaintenanceError
from .chat_history import (
    chat_history_service,
    get_chat_history as get_db_chat_history,
    save_model_response,
    save_user_message,
)
from .reminder import reminder_service, handle_reminder_command

__all__ = [
    # AI 文字服務
    'chat_with_ai',
    'ai_text_service',
    
    # AI 圖片服務
    'analyze_image',
    'ai_image_service',
    
    # 書籤服務
    'get_chat_history',
    'save_message',
    'log_keepalive',
    'bookmark_service',

    # 資料庫服務 (SQLite)
    'db_service',
    'DatabaseMaintenanceError',
    'chat_history_service',
    'get_db_chat_history',
    'save_model_response',
    'save_user_message',

    # 排程提醒
    'reminder_service',
    'handle_reminder_command',
]
