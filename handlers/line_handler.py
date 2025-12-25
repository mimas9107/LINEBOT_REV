"""
LINE Handler Module
版本: rev1
處理 LINE Webhook 事件
"""

import os
import requests
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
from services import chat_with_ai, analyze_image, get_chat_history, save_message


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
            
            # 取得使用者資訊
            user_id = self._get_user_id(event)
            timestamp = event.timestamp
            message_type = event.message.type
            message_text = ""
            result = ""
            
            # 根據訊息類型處理
            if message_type == 'text':
                message_text = event.message.text
                result = self._handle_text_message(event, user_id)
                
            elif message_type == 'image':
                result = self._handle_image_message(event)
            
            # 回覆訊息（如果有結果）
            if result:
                self._reply_message(line_bot_api, event.reply_token, result)
                print(f"{timestamp} msg from {event.source}: {getattr(event.message, 'text', '[image]')}")
            
            # 儲存訊息到 Google Sheet
            save_message(timestamp, user_id, message_type, message_text)
    
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
    
    def _handle_text_message(self, event: MessageEvent, user_id: str) -> str:
        """
        處理文字訊息
        
        Args:
            event: LINE 訊息事件
            user_id: 使用者 ID
        
        Returns:
            回覆內容
        """
        text = event.message.text
        print(f"[LineHandler] Received text message: {event.message.id}")
        
        # AI 對話模式：以 "ai:" 開頭
        if text.lower().startswith("ai:"):
            prompt = text[3:].strip()
            
            # 取得歷史對話
            chat_history = get_chat_history(user_id)
            print(f"[LineHandler] Chat history: {chat_history}")
            
            # 格式化歷史對話
            formatted_history = self._format_chat_history(chat_history, user_id)
            
            # 建立完整 prompt
            full_prompt = f"{formatted_history}User: {prompt}" if formatted_history else prompt
            print(f"[LineHandler] Full prompt: {full_prompt}")
            
            # 呼叫 AI
            result = chat_with_ai(full_prompt)
            print(f"[LineHandler] AI result: {result[:100]}...")
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
            if entry.get('userId') == current_user_id:
                formatted += f"User: {entry.get('messageText', '')}\n"
            else:
                formatted += f"Bot: {entry.get('messageText', '')}\n"
        
        print(f"[LineHandler] Formatted history: {formatted}")
        return formatted
    
    def _handle_image_message(self, event: MessageEvent) -> str:
        """
        處理圖片訊息
        
        Args:
            event: LINE 訊息事件
        
        Returns:
            AI 分析結果
        """
        message_id = event.message.id
        print(f"[LineHandler] Received image message: {message_id}")
        
        # 下載圖片
        image_path = self._download_image(message_id)
        if not image_path:
            return "圖片下載失敗，請稍後再試。"
        
        print(f"[LineHandler] Image saved to: {image_path}")
        
        # 分析圖片
        result = analyze_image(image_path)
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
            
            image_path = config.DOWNLOAD_IMAGE_PATH
            
            # 確保目錄存在
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content():
                    f.write(chunk)
            
            return image_path
            
        except Exception as e:
            print(f"[LineHandler] Error downloading image: {e}")
            return ""
    
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
