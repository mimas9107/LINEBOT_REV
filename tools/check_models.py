"""
Gemini Model Checker (修正版)
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
            # 移除 'models/' 前綴
            # 注意: 根據 SDK 版本，名稱可能是 model.name 或 model.model_id
            name = getattr(model, 'name', '未知名稱')
            display_name = getattr(model, 'display_name', '未知顯示名稱')
            
            clean_name = name.replace('models/', '')
            
            # 我們列出所有含有 'gemini' 字樣的模型，這通常就是您需要的
            if 'gemini' in clean_name.lower():
                print(f"{clean_name:<40} | {display_name}")
            
        print("-" * 80)
        print(f"總共發現 {len(models)} 個模型實體。\n")
        
    except Exception as e:
        import traceback
        print(f"查詢時發生錯誤: {e}")
        # 如果還是報錯，印出詳細堆疊資訊以便除錯
        # traceback.print_exc()

if __name__ == "__main__":
    list_models()
