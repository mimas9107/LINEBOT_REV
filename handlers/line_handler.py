"""
LINE Handler Module
版本: rev2.4.4
處理 LINE Webhook 事件

更新紀錄:
- rev2.3.3: 歷史訊息單則長度截斷（MAX_HISTORY_MSG_LEN=1000），避免長回覆線性膨脹 prompt
- rev2.3.1: AI/圖片分析失敗時跳過 SQLite 與 Sheet 寫入，僅回覆友善提示（防歷史污染）
- rev2.2: AI 對話與圖片分析寫入 SQLite，保留 Google Sheet 非同步記錄與 message_id 圖片路徑
- rev2: 配合 AI 模組更新
- rev2.1.1: save_message 改為非同步、新增 bot 回覆儲存、圖片路徑改用 message_id
"""

import os
import requests
import threading
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent

from config import config
from services import chat_with_ai, analyze_image, get_chat_history, save_message, handle_reminder_command
from services.chat_history import (
    get_chat_history as get_db_chat_history,
    save_model_response,
    save_user_message,
)
from services.logctx import set_msgid, prefix

# 單則歷史訊息納入 prompt 的長度上限（字元）
MAX_HISTORY_MSG_LEN = 1000


class LineHandler:
    """LINE 事件處理器"""
    
    def __init__(self):
        self.configuration = Configuration(access_token=config.LINE_CHANNEL_ACCESS_TOKEN)
        self.webhook_handler = WebhookHandler(config.LINE_CHANNEL_SECRET)
        
        # 註冊事件處理器
        self._register_handlers()
    
    def _register_handlers(self):
        """註冊 LINE 事件處理器"""
        
        @self.webhook_handler.add(MessageEvent)
        def handle_message(event):
            self._handle_message_event(event)
    
    def handle(self, body: str, signature: str):
        """
        處理 Webhook 請求
        
        Args:
            body: 請求內容
            signature: LINE 簽章
        """
        self.webhook_handler.handle(body, signature)
    
    def _handle_message_event(self, event: MessageEvent):
        """
        處理訊息事件
        
        Args:
            event: LINE 訊息事件
        """
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            
            # 以 message id 作為整條處理生命線的追蹤錨點
            set_msgid(getattr(event.message, "id", ""))
            
            # 取得使用者資訊
            user_id = self._get_user_id(event)
            timestamp = event.timestamp
            message_type = event.message.type
            message_text = ""
            result = ""
            
            # 根據訊息類型處理
            if message_type == 'text':
                message_text = event.message.text
                result = self._handle_text_message(event, user_id, timestamp)
                
            elif message_type == 'image':
                message_text = "[圖片]"
                result = self._handle_image_message(event, user_id)
            
            # 回覆訊息（如果有結果）
            if result:
                self._reply_message(line_bot_api, event.reply_token, result)
                print(f"{timestamp} msg from {event.source}: {getattr(event.message, 'text', '[image]')} -> replied [{len(result)} chars]")
            
            # 儲存訊息到 Google Sheet (非同步，不阻塞主線程)
            threading.Thread(
                target=save_message,
                args=(timestamp, user_id, message_type, message_text),
                daemon=True
            ).start()
    
    def _get_user_id(self, event: MessageEvent) -> str:
        """
        從事件中取得使用者 ID
        
        Args:
            event: LINE 訊息事件
        
        Returns:
            使用者 ID
        """
        source = event.source
        if source.type == "user":
            return source.user_id
        elif source.type == "group":
            return source.group_id
        elif source.type == "room":
            return source.room_id
        return "unknown"
    
    def _handle_text_message(self, event: MessageEvent, user_id: str, timestamp: int) -> str:
        """
        處理文字訊息
        
        Args:
            event: LINE 訊息事件
            user_id: 使用者 ID
            timestamp: 訊息時間戳記
        
        Returns:
            回覆內容
        """
        text = event.message.text
        print(f"[LineHandler] {prefix()}Received text message: {event.message.id}")

        # 排程提醒：自然語言偵測
        if '提醒' in text or text.lower().startswith('remind'):
            result = handle_reminder_command(user_id, text)
            return result

        # AI 對話模式：以 "ai:" 開頭
        if text.lower().startswith("ai:"):
            prompt = text[3:].strip()
            
            # 先讀取既有 SQLite 歷史，避免把本次 prompt 重複塞進完整 prompt。
            chat_history = self._get_db_history_with_fallback(user_id)
            print(f"[LineHandler] {prefix()}DB chat history count: {len(chat_history)}")
            
            # 格式化歷史對話
            formatted_history = self._format_chat_history(chat_history, user_id)
            
            # 建立完整 prompt
            full_prompt = f"{formatted_history}User: {prompt}" if formatted_history else prompt
            print(f"[LineHandler] {prefix()}Full prompt length: {len(full_prompt)}")

            # 儲存使用者訊息到 SQLite；失敗不阻斷回覆。
            self._save_db_user_message(user_id, prompt, 'text')

            # 呼叫 AI；失敗時不得將錯誤訊息寫入任何歷史紀錄。
            try:
                result = chat_with_ai(full_prompt)
            except Exception as e:
                print(f"[LineHandler] {prefix()}AI call failed, skip history write: {e}")
                return "伺服器繁忙，請稍後再試。"

            print(f"[LineHandler] {prefix()}AI result: {result[:100]}...")

            # 儲存 Bot 回覆到 SQLite；失敗不阻斷 LINE 回覆。
            self._save_db_model_response(user_id, result, 'text')
            
            # 儲存 Bot 回覆到歷史記錄 (非同步，不阻塞主線程)
            threading.Thread(
                target=save_message,
                args=(timestamp, "bot", "text", result),
                daemon=True
            ).start()
            
            return result
        
        # 複製模式：以 "c:" 開頭
        elif text.lower().startswith("c:"):
            return text[2:].strip()
        
        # 其他訊息不回覆
        return ""
    
    def _format_chat_history(self, history: list[dict], current_user_id: str) -> str:
        """
        格式化聊天歷史為 prompt 格式
        
        Args:
            history: 歷史對話列表
            current_user_id: 當前使用者 ID
        
        Returns:
            格式化後的歷史字串
        """
        if not history:
            return ""
        
        formatted = ""
        for entry in history:
            role = entry.get('role')
            text = entry.get('messageText', '')
            # # ponytail: 單則歷史過長時截斷，避免長 AI 回覆讓 prompt 累積過大推高逾時
            if len(text) > MAX_HISTORY_MSG_LEN:
                text = text[:MAX_HISTORY_MSG_LEN] + "…"
            if role == 'user' or entry.get('userId') == current_user_id:
                formatted += f"User: {text}\n"
            else:
                formatted += f"Assistant: {text}\n"
        
        print(f"[LineHandler] Formatted history: {formatted}")
        return formatted
    
    def _handle_image_message(self, event: MessageEvent, user_id: str) -> str:
        """
        處理圖片訊息
        
        Args:
            event: LINE 訊息事件
            user_id: 使用者 ID
        
        Returns:
            AI 分析結果
        """
        message_id = event.message.id
        print(f"[LineHandler] Received image message: {message_id}")

        self._save_db_user_message(user_id, "[上傳圖片]", 'image')
        
        # 下載圖片
        image_path = self._download_image(message_id)
        if not image_path:
            error_msg = "圖片下載失敗，請稍後再試。"
            self._save_db_model_response(user_id, error_msg, 'text')
            return error_msg
        
        print(f"[LineHandler] Image saved to: {image_path}")
        
        try:
            # 分析圖片；失敗時不得將錯誤訊息寫入歷史紀錄。
            result = analyze_image(image_path)
        except Exception as e:
            print(f"[LineHandler] Image analysis failed, skip history write: {e}")
            return "圖片分析失敗，請稍後再試。"
        finally:
            # 清理暫存圖片
            try:
                os.remove(image_path)
                print(f"[LineHandler] Cleaned up temp image: {image_path}")
            except Exception as e:
                print(f"[LineHandler] Warning: Failed to cleanup temp image: {e}")

        # 僅在分析成功時寫入 SQLite
        self._save_db_model_response(user_id, result, 'text')
        return result
    
    def _download_image(self, message_id: str) -> str:
        """
        從 LINE 下載圖片
        
        Args:
            message_id: 訊息 ID
        
        Returns:
            圖片儲存路徑，失敗則回傳空字串
        """
        try:
            url = f'https://api-data.line.me/v2/bot/message/{message_id}/content'
            headers = {"Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}"}
            
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            # 使用 message_id 作為檔名，避免並發覆蓋
            image_path = os.path.join(config.DOWNLOAD_IMAGE_DIR, f"{message_id}.jpg")
            
            # 確保目錄存在
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content():
                    f.write(chunk)
            
            return image_path
            
        except Exception as e:
            print(f"[LineHandler] Error downloading image: {e}")
            return ""

    def _get_db_history_with_fallback(self, user_id: str) -> list[dict]:
        """優先讀 SQLite 歷史；失敗時 fallback 到既有 Google Sheet history。"""
        try:
            return get_db_chat_history(user_id)
        except Exception as e:
            print(f"[LineHandler] DB history unavailable, fallback to sheet: {e}")
            return get_chat_history(user_id)

    def _save_db_user_message(
        self,
        user_id: str,
        message_text: str,
        message_type: str,
    ) -> None:
        """安全寫入使用者訊息到 SQLite。"""
        try:
            save_user_message(user_id, message_text, message_type)
        except Exception as e:
            print(f"[LineHandler] Failed to save user message to DB: {e}")

    def _save_db_model_response(
        self,
        user_id: str,
        message_text: str,
        message_type: str,
    ) -> None:
        """安全寫入模型回覆到 SQLite。"""
        try:
            save_model_response(user_id, message_text, message_type)
        except Exception as e:
            print(f"[LineHandler] Failed to save model response to DB: {e}")
    
    def _reply_message(self, api: MessagingApi, reply_token: str, text: str):
        """
        回覆訊息
        
        Args:
            api: LINE Messaging API
            reply_token: 回覆 token
            text: 回覆內容
        """
        api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )


# 建立全域處理器實例
line_handler = LineHandler()
