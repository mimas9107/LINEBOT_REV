"""
Services Package
版本: rev2
提供各項服務功能

更新紀錄:
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
]
