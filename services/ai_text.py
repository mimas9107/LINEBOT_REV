"""
AI Text Service Module
版本: rev1
處理 Gemini 文字對話功能
"""

import google.generativeai as genai
from config import config


class AITextService:
    """Gemini 文字對話服務"""
    
    def __init__(self):
        self._configured = False
        self._model = None
    
    def _ensure_configured(self):
        """確保 Gemini API 已設定"""
        if not self._configured:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self._configured = True
    
    def _get_model(self):
        """取得或建立模型實例"""
        if self._model is None:
            self._ensure_configured()
            generation_config = {
                "temperature": 1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }
            self._model = genai.GenerativeModel(
                model_name=config.GEMINI_TEXT_MODEL,
                generation_config=generation_config,
            )
        return self._model
    
    def chat(self, prompt: str, history: list[dict] = None) -> str:
        """
        發送訊息給 Gemini 並取得回應
        
        Args:
            prompt: 使用者輸入的訊息
            history: 歷史對話記錄 (可選)
        
        Returns:
            AI 回應的文字
        """
        try:
            model = self._get_model()
            
            # 建立聊天 session
            chat_session = model.start_chat(history=[])
            
            # 組合完整的 prompt（含歷史）
            full_prompt = self._build_prompt_with_history(prompt, history)
            
            response = chat_session.send_message(full_prompt)
            return response.text
            
        except Exception as e:
            print(f"[AITextService] Error: {e}")
            return f"AI 處理發生錯誤: {str(e)}"
    
    def _build_prompt_with_history(self, prompt: str, history: list[dict] = None) -> str:
        """
        將歷史對話與當前訊息組合成完整 prompt
        
        Args:
            prompt: 當前使用者訊息
            history: 歷史對話記錄，格式為 [{"userId": "...", "messageText": "..."}]
        
        Returns:
            組合後的完整 prompt
        """
        if not history:
            return prompt
        
        formatted_history = ""
        for entry in history:
            # 假設 history 中的 userId 與當前使用者相同表示是使用者訊息
            role = "User" if entry.get("userId") else "Bot"
            formatted_history += f"{role}: {entry.get('messageText', '')}\n"
        
        return f"{formatted_history}User: {prompt}"


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
