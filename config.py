"""
LINEBOT Configuration Module
版本: rev1
統一管理所有環境變數與設定
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """應用程式設定類別"""
    
    # LINE Bot 設定
    LINE_CHANNEL_ACCESS_TOKEN: str = ""
    LINE_CHANNEL_SECRET: str = ""
    
    # Gemini AI 設定
    GEMINI_API_KEY: str = ""
    GEMINI_TEXT_MODEL: str = "gemini-2.5-flash"
    GEMINI_IMAGE_MODEL: str = "gemini-2.0-flash-exp"
    
    # Google Apps Script 設定
    GOOGLE_APPS_SCRIPT_URL: str = ""
    
    # 聊天歷史設定
    CHAT_HISTORY_LENGTH: int = 5
    
    # 本地 LMStudio 設定 (備用)
    LMSTUDIO_URL: str = "https://c8jkzw1b-3030.asse.devtunnels.ms/v1/chat/completions"
    LMSTUDIO_MODEL: str = "llava-v1.5-7b"
    
    # 圖片儲存路徑
    DOWNLOAD_IMAGE_PATH: str = "pic/downloadimg.jpg"
    
    # Keepalive 設定
    KEEPALIVE_INTERVAL: int = 780  # 13 分鐘
    SELF_URL: str = "https://linebot-bisb.onrender.com/about"
    
    def __post_init__(self):
        """從環境變數載入設定"""
        self.LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
        self.LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        self.GOOGLE_APPS_SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL", "")
    
    def validate(self) -> list[str]:
        """驗證必要設定是否存在，回傳缺少的設定名稱列表"""
        missing = []
        if not self.LINE_CHANNEL_ACCESS_TOKEN:
            missing.append("LINE_CHANNEL_ACCESS_TOKEN")
        if not self.LINE_CHANNEL_SECRET:
            missing.append("LINE_CHANNEL_SECRET")
        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        return missing


# 全域設定實例
config = Config()
