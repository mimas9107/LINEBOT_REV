"""
LINEBOT Configuration Module
版本: rev2.3.3
統一管理所有環境變數與設定

更新紀錄:
- rev2.3.2: max_output_tokens 4096、log 顯示 active model
- rev2.3.1: 新增 MODEL_LIST 候選模型 fallback 清單（503/429 容錯）
- rev2.2.1: keepalive 只在直接執行時啟動，配合 patch release 說明同步
- rev2.3.0: 新增 REMINDER_CHECK_INTERVAL、MAX_PENDING_REMINDERS 設定
- rev2.2: 新增 SQLite 資料庫設定、API 金鑰設定，並補齊所有 config 屬性的環境變數覆蓋與型別轉換
- rev2.1: 更新 Gemini 模型為長效別名 gemini-flash-latest，確保穩定服務
- rev2: 更新為 google-genai SDK，統一使用 gemini-flash-latest 模型
- rev2.1.1: 所有 save_message 改為非同步、圖片路徑改用 message_id、新增 bot 回覆儲存
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """應用程式設定類別"""
    
    # LINE Bot 設定
    LINE_CHANNEL_ACCESS_TOKEN: str = ""
    LINE_CHANNEL_SECRET: str = ""
    
    # Gemini AI 設定 (使用新版 google-genai SDK)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"  # 改用長效別名，由 Google 自動管理版本

    # SQLite 資料庫設定
    DATABASE_PATH: str = "data/chat_history.db"

    # API 安全設定 (用於資料庫查詢/下載 API)
    API_SECRET_KEY: str = ""
    
    # Google Apps Script 設定
    GOOGLE_APPS_SCRIPT_URL: str = ""
    
    # 聊天歷史設定
    CHAT_HISTORY_LENGTH: int = 5
    
    # 本地 LMStudio 設定 (備用)
    LMSTUDIO_URL: str = "https://c8jkzw1b-3030.asse.devtunnels.ms/v1/chat/completions"
    LMSTUDIO_MODEL: str = "llava-v1.5-7b"
    
    # 圖片儲存目錄 (檔名由 message_id 動態產生)
    DOWNLOAD_IMAGE_DIR: str = "pic"
    
    # Keepalive 設定
    KEEPALIVE_INTERVAL: int = 780  # 13 分鐘
    SELF_URL: str = "https://linebot-rev.onrender.com/about"

    # 排程提醒設定
    REMINDER_CHECK_INTERVAL: int = 30  # 秒
    MAX_PENDING_REMINDERS: int = 20  # 每人最多待處理提醒數
    
    def __post_init__(self):
        """從環境變數載入設定"""
        self.LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", self.LINE_CHANNEL_ACCESS_TOKEN)
        self.LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", self.LINE_CHANNEL_SECRET)
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", self.GEMINI_API_KEY)
        self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", self.GEMINI_MODEL)
        self.DATABASE_PATH = os.getenv("DATABASE_PATH", self.DATABASE_PATH)
        self.API_SECRET_KEY = os.getenv("API_SECRET_KEY", self.API_SECRET_KEY)
        self.GOOGLE_APPS_SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL", self.GOOGLE_APPS_SCRIPT_URL)
        self.CHAT_HISTORY_LENGTH = self._get_int_env("CHAT_HISTORY_LENGTH", self.CHAT_HISTORY_LENGTH)
        self.LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", self.LMSTUDIO_URL)
        self.LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", self.LMSTUDIO_MODEL)
        self.DOWNLOAD_IMAGE_DIR = os.getenv("DOWNLOAD_IMAGE_DIR", self.DOWNLOAD_IMAGE_DIR)
        self.KEEPALIVE_INTERVAL = self._get_int_env("KEEPALIVE_INTERVAL", self.KEEPALIVE_INTERVAL)
        self.SELF_URL = os.getenv("SELF_URL", self.SELF_URL)
        self.REMINDER_CHECK_INTERVAL = self._get_int_env("REMINDER_CHECK_INTERVAL", self.REMINDER_CHECK_INTERVAL)
        self.MAX_PENDING_REMINDERS = self._get_int_env("MAX_PENDING_REMINDERS", self.MAX_PENDING_REMINDERS)

    @staticmethod
    def _get_int_env(name: str, default: int) -> int:
        """讀取整數環境變數，無效時保留預設值。"""
        raw_value = os.getenv(name)
        if raw_value is None or raw_value == "":
            return default
        try:
            return int(raw_value)
        except ValueError:
            print(f"[WARNING] Invalid integer for {name}: {raw_value}. Using default: {default}")
            return default
    
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

# Gemini 候選模型 fallback 清單：依序嘗試；markfail=True 的模型失敗後於冷卻期內跳過。
MODEL_LIST = [
    {"model": "gemini-flash-latest", "markfail": True},
    {"model": "gemini-2.5-flash", "markfail": False},
    {"model": "gemini-1.5-flash", "markfail": False},
    {"model": "gemini-1.5-pro", "markfail": False},
]
