"""
Services Package
版本: rev3.1
提供各項服務功能

更新紀錄:
- rev3.1: 新增 maintenance mode、restore 功能
- rev3: 新增 SQLite 對話歷史記錄 (database.py, chat_history.py)
- rev2: AI 模組改用 google-genai SDK
"""

from .ai_text import chat_with_ai, ai_text_service
from .ai_image import analyze_image, ai_image_service
from .bookmark import (
    get_chat_history as get_sheet_history,
    save_message as save_to_sheet,
    log_keepalive,
    bookmark_service
)
from .database import db_service, DatabaseMaintenanceError, DatabaseRestoreError
from .chat_history import (
    chat_history_service,
    save_user_message,
    save_model_response,
    get_chat_history,
)

__all__ = [
    # AI 文字服務
    'chat_with_ai',
    'ai_text_service',
    
    # AI 圖片服務
    'analyze_image',
    'ai_image_service',
    
    # 書籤服務 (Google Sheet)
    'get_sheet_history',
    'save_to_sheet',
    'log_keepalive',
    'bookmark_service',
    
    # 資料庫服務 (SQLite)
    'db_service',
    'DatabaseMaintenanceError',
    'DatabaseRestoreError',
    
    # 對話歷史服務 (SQLite)
    'chat_history_service',
    'save_user_message',
    'save_model_response',
    'get_chat_history',
]
