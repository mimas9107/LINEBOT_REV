"""
LINEBOT Application
版本: rev2.3.3
Flask 應用程式入口點

更新紀錄:
- rev2.3.3: 版本化 Procfile（--timeout 300）、圖片路徑新增 MODEL_LIST 容錯
- rev2.3.2: Gemini 回應加速（max_output_tokens 4096）、log 顯示 active model、gunicorn timeout 300s
- rev2.3.1: AI 503/429 容錯（MODEL_LIST fallback + markfail 冷卻）與對話歷史防污染
- rev2.2.1: 延後 keepalive 到第一個請求才啟動，避免 worker import 階段搶資源
- rev2.3.0: 新增 APScheduler 排程提醒系統 (reminders table + LINE Push)
- rev2.2: 新增 SQLite database 只讀/下載 API，明確停用上傳還原端點
- rev2: AI 模組改用 google-genai SDK
"""

import os
import threading

from flask import Flask, request, abort, jsonify, send_file

from config import config
from handlers import line_handler
from services import db_service, reminder_service
from services.chat_history import chat_history_service
from utils import start_keepalive

# 驗證設定
missing_configs = config.validate()
if missing_configs:
    print(f"[WARNING] Missing configurations: {', '.join(missing_configs)}")

# 建立 Flask 應用
app = Flask(__name__)
_keepalive_started = False
_keepalive_lock = threading.Lock()


# ===== 路由定義 =====

@app.route('/')
def home():
    """首頁"""
    return 'Hello, World! LINEBOT rev2.3.3 is running.'


@app.route('/about')
def about():
    """關於頁面（也用於 keepalive ping）"""
    return '<h1>LINEBOT rev2.3.3 - Python Flask LINE Bot (google-genai SDK + SQLite + Reminder)</h1>'


@app.route('/health')
def health():
    """健康檢查端點"""
    return {
        'status': 'healthy',
        'version': 'rev2.3.3',
        'database': db_service.get_db_stats()
    }


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


# ===== API 驗證 =====

def verify_api_key():
    """驗證 API 金鑰"""
    api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    if not config.API_SECRET_KEY:
        abort(503, description="Database API is not configured")
    if not api_key or api_key != config.API_SECRET_KEY:
        abort(401, description="Invalid or missing API key")


# ===== 資料庫管理 API =====

@app.route('/api/db/download', methods=['GET'])
def download_database():
    """下載 SQLite 資料庫檔案"""
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
    return jsonify(db_service.get_db_stats())


@app.route('/api/db/export', methods=['GET'])
def export_database():
    """匯出資料庫為 JSON 格式"""
    verify_api_key()

    limit = request.args.get('limit', 1000, type=int)
    export_data = chat_history_service.export_to_dict()
    export_data['messages'] = export_data['messages'][:limit]

    return jsonify(export_data)


@app.route('/api/db/messages', methods=['GET'])
def get_messages():
    """查詢對話訊息"""
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
    """取得特定使用者的對話歷史"""
    verify_api_key()

    limit = request.args.get('limit', 50, type=int)
    history = chat_history_service.get_chat_history(user_id, limit)

    return jsonify({
        "user_id": user_id,
        "count": len(history),
        "history": history
    })


@app.route('/api/db/maintenance', methods=['GET'])
def get_maintenance_status():
    """取得維護模式狀態"""
    verify_api_key()

    return jsonify({
        "maintenance_mode": db_service.is_maintenance,
        "reason": db_service.maintenance_reason
    })


@app.route('/api/db/restore', methods=['POST'])
@app.route('/api/db/validate', methods=['POST'])
def database_upload_disabled():
    """停用所有資料庫上傳型端點，避免 Render 實例因還原流程當機。"""
    verify_api_key()
    return jsonify({
        "success": False,
        "error": "Database upload/restore endpoints are disabled on this deployment.",
        "disabled": True
    }), 403


# ===== 啟動保活 =====

@app.before_request
def ensure_keepalive_started():
    """延後到第一個請求才啟動 keepalive，避免 worker boot 階段搶資源。"""
    global _keepalive_started

    if _keepalive_started:
        return None

    with _keepalive_lock:
        if not _keepalive_started:
            start_keepalive()
            reminder_service.start()
            _keepalive_started = True

    return None


# ===== 啟動應用 =====

if __name__ == '__main__':
    app.run(debug=True)
