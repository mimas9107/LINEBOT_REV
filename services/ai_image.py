"""
AI Image Service Module
版本: rev1
處理 Gemini 圖片辨識功能
"""

import base64
import requests
import PIL.Image
from google import genai
from config import config


class AIImageService:
    """Gemini 圖片辨識服務"""
    
    def __init__(self):
        self._client = None
    
    def _get_client(self):
        """取得或建立 Gemini client"""
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
            image = PIL.Image.open(image_path)
            client = self._get_client()
            
            response = client.models.generate_content(
                model=config.GEMINI_IMAGE_MODEL,
                contents=[prompt, image]
            )
            
            return f"你上傳了一張圖,\nAI 回答:\n{response.text}"
            
        except Exception as e:
            print(f"[AIImageService] Gemini Error: {e}")
            return f"圖片分析發生錯誤: {str(e)}"
    
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
