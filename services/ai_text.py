"""
AI Text Service Module
版本: rev3.1
處理 Gemini 文字對話功能
"""

from google import genai
from google.genai import types
from config import config


class AITextService:
    """Gemini 文字對話服務 (使用新版 google-genai SDK)"""
    
    def __init__(self):
        self._client = None
    
    def _get_client(self) -> genai.Client:
        """取得或建立 Gemini Client"""
        if self._client is None:
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        return self._client
    
    def chat(self, prompt: str, history: list[dict] = None) -> str:
        """
        發送訊息給 Gemini 並取得回應
        
        Args:
            prompt: 使用者輸入的訊息
            history: 歷史對話記錄 (可選)，格式為 [{"userId": "...", "messageText": "..."}]
        
        Returns:
            AI 回應的文字
        """
        try:
            client = self._get_client()
            
            # 如果有歷史對話，使用 chats API
            if history:
                return self._chat_with_history(client, prompt, history)
            
            # 單次對話直接使用 generate_content
            return self._single_generate(client, prompt)
            
        except Exception as e:
            print(f"[AITextService] Error: {e}")
            return f"AI 處理發生錯誤: {str(e)}"
    
    def _single_generate(self, client: genai.Client, prompt: str) -> str:
        """
        單次生成回應 (無歷史對話)
        
        Args:
            client: Gemini Client
            prompt: 使用者訊息
        
        Returns:
            AI 回應
        """
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=1.0,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
            )
        )
        return response.text
    
    def _chat_with_history(self, client: genai.Client, prompt: str, history: list[dict]) -> str:
        """
        帶有歷史對話的聊天
        
        Args:
            client: Gemini Client
            prompt: 當前使用者訊息
            history: 歷史對話記錄
        
        Returns:
            AI 回應
        """
        # 將歷史對話轉換為 SDK 格式
        chat_history = self._convert_history_to_contents(history)
        
        # 建立 chat session
        chat = client.chats.create(
            model=config.GEMINI_MODEL,
            history=chat_history,
            config=types.GenerateContentConfig(
                temperature=1.0,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
            )
        )
        
        # 發送訊息
        response = chat.send_message(prompt)
        return response.text
    
    def _convert_history_to_contents(self, history: list[dict]) -> list[types.Content]:
        """
        將自訂歷史格式轉換為 SDK Content 格式
        
        Args:
            history: 歷史對話，格式為 [{"userId": "...", "messageText": "..."}]
                     假設相同 userId 為 user，不同則為 model
        
        Returns:
            SDK Content 列表
        """
        if not history:
            return []
        
        contents = []
        
        # 取得第一個 userId 作為 user 的基準
        user_id = history[0].get('userId', '') if history else ''
        
        for entry in history:
            message_text = entry.get('messageText', '')
            if not message_text:
                continue
            
            # 判斷角色：相同 userId 為 user，不同為 model
            role = 'user' if entry.get('userId') == user_id else 'model'
            
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=message_text)]
                )
            )
        
        return contents
    
    def generate_simple(self, prompt: str) -> str:
        """
        簡單生成回應 (便捷方法)
        
        Args:
            prompt: 提示文字
        
        Returns:
            AI 回應
        """
        try:
            client = self._get_client()
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"[AITextService] Simple generate error: {e}")
            return f"AI 處理發生錯誤: {str(e)}"


# 建立全域服務實例
ai_text_service = AITextService()


def chat_with_ai(prompt: str, history: list[dict] = None) -> str:
    """
    便捷函式：發送訊息給 AI
    
    Args:
        prompt: 使用者訊息
        history: 歷史對話 (可選)
    
    Returns:
        AI 回應
    """
    return ai_text_service.chat(prompt, history)
