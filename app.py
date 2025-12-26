"""
LINEBOT Application
版本: rev3
Flask 應用程式入口點

更新紀錄:
- rev3: 新增 SQLite 對話記錄系統，新增資料庫下載/查詢 API
- rev2: AI 模組改用 google-genai SDK
"""

import os
from flask import Flask, request, abort, jsonify, send_file

from config import config
from handlers import line_handler
from utils import start_keepalive
from services import db_service
from services.chat_history import chat_history_service

# 驗證設定
missing_configs = config.validate()
if missing_configs:
    print(f"[WARNING] Missing configurations: {', '.join(missing_configs)}")

# 建立 Flask 應用
app = Flask(__name__)


# ===== 基本路由 =====

@app.route('/')
def home():
    """首頁"""
    return 'Hello, World! LINEBOT rev3 is running.'


@app.route('/about')
def about():
    """關於頁面（也用於 keepalive ping）"""
    return '<h1>LINEBOT rev3 - Python Flask LINE Bot (SQLite Edition)</h1>'


@app.route('/health')
def health():
    """健康檢查端點"""
    stats = db_service.get_db_stats()
    return {
        'status': 'healthy',
        'version': 'rev3',
        'database': stats
    }


# ===== LINE Webhook =====

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


# ===== 資料庫管理 API =====

def verify_api_key():
    """驗證 API 金鑰"""
    api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if not api_key or api_key != config.API_SECRET_KEY:
        abort(401, description="Invalid or missing API key")


@app.route('/api/db/download', methods=['GET'])
def download_database():
    """
    下載 SQLite 資料庫檔案
    
    需要 API Key 驗證：
    - Header: X-API-Key
    - 或 Query: ?api_key=xxx
    """
    verify_api_key()
    
    db_path = config.DATABASE_PATH
    if not os.path.exists(db_path):
        return jsonify({"error": "Database not found"}), 404
    
    return send_file(
        db_path,
        as_attachment=True,
        download_name='chat_history.db',
        mimetype='application/x-sqlite3'
    )


@app.route('/api/db/stats', methods=['GET'])
def get_database_stats():
    """取得資料庫統計資訊"""
    verify_api_key()
    
    stats = db_service.get_db_stats()
    return jsonify(stats)


@app.route('/api/db/export', methods=['GET'])
def export_database():
    """
    匯出資料庫為 JSON 格式
    
    Query params:
    - limit: 訊息數量上限 (預設 1000)
    """
    verify_api_key()
    
    limit = request.args.get('limit', 1000, type=int)
    
    export_data = chat_history_service.export_to_dict()
    export_data['messages'] = export_data['messages'][:limit]
    
    return jsonify(export_data)


@app.route('/api/db/messages', methods=['GET'])
def get_messages():
    """
    查詢對話訊息
    
    Query params:
    - user_id: 篩選特定使用者
    - limit: 數量上限 (預設 100)
    - offset: 起始位置 (預設 0)
    """
    verify_api_key()
    
    user_id = request.args.get('user_id')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    if user_id:
        messages = chat_history_service.get_user_messages(user_id, limit)
    else:
        messages = chat_history_service.get_all_messages(limit, offset)
    
    return jsonify({
        "count": len(messages),
        "messages": messages
    })


@app.route('/api/db/users', methods=['GET'])
def get_users():
    """取得所有使用者統計"""
    verify_api_key()
    
    users = chat_history_service.get_unique_users()
    return jsonify({
        "count": len(users),
        "users": users
    })


@app.route('/api/db/user/<user_id>/history', methods=['GET'])
def get_user_history(user_id: str):
    """
    取得特定使用者的對話歷史
    
    Path params:
    - user_id: 使用者 ID
    
    Query params:
    - limit: 數量上限 (預設 50)
    """
    verify_api_key()
    
    limit = request.args.get('limit', 50, type=int)
    history = chat_history_service.get_chat_history(user_id, limit)
    
    return jsonify({
        "user_id": user_id,
        "count": len(history),
        "history": history
    })


# ===== 啟動應用 =====

# 啟動 keepalive 背景任務
start_keepalive()

if __name__ == '__main__':
    app.run(debug=True)
