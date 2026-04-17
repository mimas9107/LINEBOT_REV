"""
Gemini Model Checker
用途: 查詢目前 API Key 可用的模型列表
"""

from google import genai
import os
from dotenv import load_dotenv

def list_models():
    # 載入環境變數
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("錯誤: 找不到 GEMINI_API_KEY 環境變數。")
        return

    try:
        client = genai.Client(api_key=api_key)
        
        print(f"\n{'模型 ID (用於 config.py)':<40} | {'顯示名稱'}")
        print("-" * 80)
        
        # 取得所有模型
        models = list(client.models.list())
        
        for model in models:
            name = getattr(model, 'name', '未知名稱')
            display_name = getattr(model, 'display_name', '未知顯示名稱')
            
            clean_name = name.replace('models/', '')
            
            # 列出所有包含 gemini 的模型
            if 'gemini' in clean_name.lower():
                print(f"{clean_name:<40} | {display_name}")
            
        print("-" * 80)
        print(f"總共發現 {len(models)} 個模型實體。\n")
        
    except Exception as e:
        print(f"查詢時發生錯誤: {e}")

if __name__ == "__main__":
    list_models()
