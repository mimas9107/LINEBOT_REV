"""
AI Text Service Module
版本: rev2.3.2
處理 Gemini 文字對話功能

更新紀錄:
- rev2.3.2: max_output_tokens 4096、成功時 log 顯示 active model
- rev2.3.1: 新增 MODEL_LIST fallback（503/429 退避重試 + markfail 冷卻）；失敗改為拋出例外，不再回傳錯誤字串
- rev2: 改用 google-genai SDK (新版統一 SDK)
      - 使用 genai.Client() 取代 genai.configure()
      - 使用 client.models.generate_content() 取代 model.generate_content()
      - 使用 client.chats.create() 支援多輪對話
- rev2.1.1: 修正歷史對話角色判斷邏輯，userId="bot" 識別為 model 角色
"""

import time

from google import genai
from google.genai import types
from config import config, MODEL_LIST


class AITextService:
    """Gemini 文字對話服務 (使用新版 google-genai SDK)"""

    # fallback 設定
    RETRY_COUNT = 2       # 每個模型遇到 503/429 時的額外重試次數
    BACKOFF_BASE = 1.5    # 退避基數（秒），間隔 = BACKOFF_BASE * attempt
    FAIL_COOLDOWN = 600   # markfail=True 的模型失敗後的冷卻秒數
    RETRYABLE_CODES = (503, 429)

    def __init__(self):
        self._client = None
        self._failed_marks = {}  # model -> 失敗時間（time.monotonic）
    
    def _get_client(self) -> genai.Client:
        """取得或建立 Gemini Client"""
        if self._client is None:
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        return self._client
    
    def chat(self, prompt: str, history: list[dict] = None) -> str:
        """
        發送訊息給 Gemini 並取得回應

        失敗時拋出例外（不再回傳錯誤字串）；呼叫端不得將例外訊息寫入對話歷史。

        Args:
            prompt: 使用者輸入的訊息
            history: 歷史對話記錄 (可選)，格式為 [{"userId": "...", "messageText": "..."}]

        Returns:
            AI 回應的文字
        """
        client = self._get_client()

        # 如果有歷史對話，使用 chats API
        if history:
            return self._chat_with_history(client, prompt, history)

        response = self._generate(
            contents=prompt,
            gen_config=types.GenerateContentConfig(
                temperature=1.0,
                top_p=0.95,
                top_k=40,
                max_output_tokens=4096,
            )
        )
        return response.text

    def _generate(self, contents, gen_config):
        """
        依 config.MODEL_LIST 依序嘗試候選模型。

        - 503/429：每模型重試 RETRY_COUNT 次，間隔 BACKOFF_BASE * attempt 秒
        - 其他例外：不重試，直接換下一個候選模型
        - markfail=True 的模型失敗後標記，FAIL_COOLDOWN 秒內的請求直接跳過
        - 全部候選失敗時拋出 RuntimeError
        """
        last_error = None
        now = time.monotonic()
        for candidate in MODEL_LIST:
            model = candidate["model"]
            if candidate.get("markfail"):
                failed_at = self._failed_marks.get(model)
                if failed_at is not None and now - failed_at < self.FAIL_COOLDOWN:
                    print(f"[AITextService] Skip {model} (markfail cooldown)")
                    continue

            for attempt in range(self.RETRY_COUNT + 1):
                try:
                    response = self._get_client().models.generate_content(
                        model=model,
                        contents=contents,
                        config=gen_config,
                    )
                    self._failed_marks.pop(model, None)
                    print(f"[AITextService] current model={model} -> OK")
                    return response
                except Exception as e:
                    last_error = e
                    print(f"[AITextService] {model} attempt {attempt + 1}/{self.RETRY_COUNT + 1} failed: {e}")
                    if not self._is_retryable(e):
                        break
                    if attempt < self.RETRY_COUNT:
                        time.sleep(self.BACKOFF_BASE * (attempt + 1))

            if candidate.get("markfail"):
                self._failed_marks[model] = time.monotonic()

        raise RuntimeError(f"AI 服務暫時不可用: {last_error}") from last_error

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        """僅 503 UNAVAILABLE / 429 RATE_LIMIT 視為可重試。"""
        return getattr(error, "code", None) in AITextService.RETRYABLE_CODES
    
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
                max_output_tokens=4096,
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
                     userId 為 "bot" 表示 AI 回覆，其他為使用者
        
        Returns:
            SDK Content 列表
        """
        if not history:
            return []
        
        contents = []
        
        for entry in history:
            message_text = entry.get('messageText', '')
            if not message_text:
                continue
            
            # 判斷角色：userId 為 "bot" 為 model，其他為 user
            role = 'model' if entry.get('userId') == 'bot' else 'user'
            
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=message_text)]
                )
            )
        
        return contents
    
    def generate_simple(self, prompt: str) -> str:
        """
        簡單生成回應 (便捷方法)，失敗時拋出例外。

        Args:
            prompt: 提示文字

        Returns:
            AI 回應
        """
        response = self._generate(contents=prompt, gen_config=None)
        return response.text


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
