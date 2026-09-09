"""
AI Image Service Module
版本: rev2.4.4
處理 Gemini 圖片辨識功能

更新紀錄:
- rev2.3.3: 圖片路徑加入 MODEL_LIST fallback + 503/429 退避重試 + markfail 冷卻（比照 ai_text）
- rev2.3.1: 分析失敗改為拋出例外，不再回傳錯誤字串（防歷史污染）
- rev2: 改用 google-genai SDK (新版統一 SDK)
      - 使用 genai.Client() 統一管理
      - 使用 types.Part.from_bytes() 處理圖片
      - 統一使用 gemini-flash-latest 模型 (長效別名，支援多模態)
"""

import base64
import time
import requests
import PIL.Image
from google import genai
from google.genai import types
from config import config, MODEL_LIST

# # ponytail: 直接檔案載入測試會避開 services/__init__（其匯入 apscheduler），故用防衛式匯入
try:
    from services.logctx import prefix
except Exception:  # pragma: no cover
    prefix = lambda: ""


class AIImageService:
    """Gemini 圖片辨識服務 (使用新版 google-genai SDK)"""

    # 容錯設定（與 AITextService 一致）
    RETRY_COUNT = 2
    BACKOFF_BASE = 1.5
    FAIL_COOLDOWN = 600
    RETRYABLE_CODES = (503, 429)

    def __init__(self):
        self._client = None
        self._failed_marks = {}  # model -> 失敗時間（time.monotonic）
    
    def _get_client(self) -> genai.Client:
        """取得或建立 Gemini Client"""
        if self._client is None:
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        return self._client
    
    def analyze_image(self, image_path: str, prompt: str = "這張圖是什麼?") -> str:
        """
        使用 Gemini 分析圖片
        
        Args:
            image_path: 圖片檔案路徑
            prompt: 詢問 AI 的問題
        
        Returns:
            AI 對圖片的分析結果
        """
        try:
            client = self._get_client()
            
            # 方法 1：使用 PIL.Image 直接傳入 (SDK 會自動處理)
            image = PIL.Image.open(image_path)
            
            response = self._generate(
                client=client,
                contents=[prompt, image],
            )
            
            return f"你上傳了一張圖,\nAI 回答:\n{response.text}"
            
        except Exception as e:
            print(f"[AIImageService] Error with PIL method: {e}")
            # 嘗試備用方法
            return self._analyze_image_with_bytes(image_path, prompt)
    
    def _analyze_image_with_bytes(self, image_path: str, prompt: str) -> str:
        """
        使用 bytes 方式分析圖片 (備用方法)
        
        Args:
            image_path: 圖片檔案路徑
            prompt: 詢問 AI 的問題
        
        Returns:
            AI 分析結果
        """
        try:
            client = self._get_client()
            
            # 讀取圖片為 bytes
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            # 判斷 MIME 類型
            mime_type = self._get_mime_type(image_path)
            
            # 使用 types.Part.from_bytes 建立圖片 Part
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            )
            
            response = self._generate(
                client=client,
                contents=[prompt, image_part],
            )
            
            return f"你上傳了一張圖,\nAI 回答:\n{response.text}"
            
        except Exception as e:
            print(f"[AIImageService] Error with bytes method: {e}")
            raise

    def _generate(self, client, contents):
        """
        依 config.MODEL_LIST 依序嘗試候選模型（比照 AITextService._generate）。

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
                    print(f"[AIImageService] {prefix()}Skip {model} (markfail cooldown)")
                    continue

            for attempt in range(self.RETRY_COUNT + 1):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                    )
                    self._failed_marks.pop(model, None)
                    print(f"[AIImageService] {prefix()}current model={model} -> OK")
                    return response
                except Exception as e:
                    last_error = e
                    print(f"[AIImageService] {prefix()}{model} attempt {attempt + 1}/{self.RETRY_COUNT + 1} failed: {e}")
                    if not self._is_retryable(e):
                        break
                    if attempt < self.RETRY_COUNT:
                        time.sleep(self.BACKOFF_BASE * (attempt + 1))

            if candidate.get("markfail"):
                self._failed_marks[model] = time.monotonic()

        raise RuntimeError(f"圖片分析服務暫時不可用: {last_error}") from last_error

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        """僅 503 UNAVAILABLE / 429 RATE_LIMIT 視為可重試。"""
        return getattr(error, "code", None) in AIImageService.RETRYABLE_CODES
    
    def _get_mime_type(self, image_path: str) -> str:
        """
        根據檔案副檔名判斷 MIME 類型
        
        Args:
            image_path: 圖片路徑
        
        Returns:
            MIME 類型字串
        """
        path_lower = image_path.lower()
        if path_lower.endswith('.png'):
            return 'image/png'
        elif path_lower.endswith('.gif'):
            return 'image/gif'
        elif path_lower.endswith('.webp'):
            return 'image/webp'
        else:
            return 'image/jpeg'  # 預設為 JPEG
    
    def analyze_image_with_lmstudio(self, image_path: str, prompt: str = "What is this image?") -> str:
        """
        使用本地 LMStudio 分析圖片 (備用方案)
        
        Args:
            image_path: 圖片檔案路徑
            prompt: 詢問 AI 的問題
        
        Returns:
            AI 對圖片的分析結果
        """
        try:
            with open(image_path, 'rb') as f:
                encoded_string = base64.b64encode(f.read()).decode('utf-8')
            
            data = {
                "model": config.LMSTUDIO_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{encoded_string}"}
                            }
                        ]
                    }
                ],
                "temperature": 0.7,
                "max_tokens": -1,
                "stream": False
            }
            
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                config.LMSTUDIO_URL,
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()['choices'][0]['message']['content']
            return f"你上傳了一張圖,\nAI 回答:\n{result}"
            
        except Exception as e:
            print(f"[AIImageService] LMStudio Error: {e}")
            return f"圖片分析發生錯誤: {str(e)}"
    
    def analyze_with_custom_prompt(self, image_path: str, prompt: str) -> str:
        """
        使用自訂 prompt 分析圖片
        
        Args:
            image_path: 圖片路徑
            prompt: 自訂問題
        
        Returns:
            AI 回應
        """
        return self.analyze_image(image_path, prompt)


# 建立全域服務實例
ai_image_service = AIImageService()


def analyze_image(image_path: str, prompt: str = "這張圖是什麼?", use_lmstudio: bool = False) -> str:
    """
    便捷函式：分析圖片
    
    Args:
        image_path: 圖片路徑
        prompt: 問題
        use_lmstudio: 是否使用本地 LMStudio
    
    Returns:
        AI 分析結果
    """
    if use_lmstudio:
        return ai_image_service.analyze_image_with_lmstudio(image_path, prompt)
    return ai_image_service.analyze_image(image_path, prompt)
