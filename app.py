"""
LINEBOT Application
版本: rev1
Flask 應用程式入口點
"""

from flask import Flask, request, abort

from config import config
from handlers import line_handler
from utils import start_keepalive

# 驗證設定
missing_configs = config.validate()
if missing_configs:
    print(f"[WARNING] Missing configurations: {', '.join(missing_configs)}")

# 建立 Flask 應用
app = Flask(__name__)


# ===== 路由定義 =====

@app.route('/')
def home():
    """首頁"""
    return 'Hello, World! LINEBOT rev1 is running.'


@app.route('/about')
def about():
    """關於頁面（也用於 keepalive ping）"""
    return '<h1>LINEBOT rev1 - Python Flask LINE Bot</h1>'


@app.route('/health')
def health():
    """健康檢查端點"""
    return {'status': 'healthy', 'version': 'rev1'}


@app.route("/callback", methods=['POST'])
def callback():
    """
    LINE Webhook 回呼端點
    接收並處理來自 LINE 的事件
    """
    # 取得 X-Line-Signature header
    signature = request.headers.get('X-Line-Signature', '')
    
    # 取得請求內容
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")
    
    # 處理 webhook
    try:
        line_handler.handle(body, signature)
    except Exception as e:
        app.logger.error(f"Error handling webhook: {e}")
        abort(400)
    
    return 'OK'


# ===== 啟動應用 =====

# 啟動 keepalive 背景任務
start_keepalive()

if __name__ == '__main__':
    app.run(debug=True)
