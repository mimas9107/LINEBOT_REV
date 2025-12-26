"""
LINEBOT Application
版本: rev3.1
Flask 應用程式入口點

更新紀錄:
- rev3.1: 新增 /api/db/restore 端點、maintenance mode 狀態
- rev3: 新增 SQLite 對話記錄系統，新增資料庫下載/查詢 API
- rev2: AI 模組改用 google-genai SDK
"""

import os
import tempfile
from flask import Flask, request, abort, jsonify, send_file

from config import config
from handlers import line_handler
from utils import start_keepalive
from services import db_service, DatabaseRestoreError
from services.chat_history import chat_history_service

# 驗證設定
missing_configs = config.validate()
if missing_configs:
    print(f"[WARNING] Missing configurations: {', '.join(missing_configs)}")

# 建立 Flask 應用
app = Flask(__name__)

# 設定最大上傳檔案大小 (16 MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


# ===== 基本路由 =====

@app.route('/')
def home():
    """首頁"""
    status = "🔧 MAINTENANCE" if db_service.is_maintenance else "✅ RUNNING"
    return f'Hello, World! LINEBOT rev3.1 is {status}.'


@app.route('/about')
def about():
    """關於頁面（也用於 keepalive ping）"""
    return '<h1>LINEBOT rev3.1 - Python Flask LINE Bot (SQLite + Restore)</h1>'


@app.route('/health')
def health():
    """健康檢查端點"""
    stats = db_service.get_db_stats()
    return {
        'status': 'maintenance' if db_service.is_maintenance else 'healthy',
        'version': 'rev3.1',
        'database': stats
    }


# ===== LINE Webhook =====

@app.route("/callback", methods=['POST'])
def callback():
    """
    LINE Webhook 回呼端點
    接收並處理來自 LINE 的事件
    """
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")
    
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
    stats = db_service.get_db_stats()
    return jsonify(stats)


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


# ===== Restore API (rev3.1 新增) =====

@app.route('/api/db/maintenance', methods=['GET'])
def get_maintenance_status():
    """取得維護模式狀態"""
    verify_api_key()
    
    return jsonify({
        "maintenance_mode": db_service.is_maintenance,
        "reason": db_service.maintenance_reason
    })


@app.route('/api/db/restore', methods=['POST'])
def restore_database():
    """
    還原資料庫
    
    上傳 SQLite 檔案來還原資料庫。
    
    流程：
    1. 設定 maintenance mode（停止接收新訊息）
    2. 等待 2 秒讓進行中的請求完成
    3. 驗證上傳的 SQLite 檔案
    4. 備份現有資料庫
    5. 原子替換資料庫檔案
    6. 執行 WAL checkpoint 和 VACUUM
    7. 解除 maintenance mode
    
    若失敗會自動 rollback 到備份。
    
    Request:
        Content-Type: multipart/form-data
        file: SQLite 資料庫檔案 (.db)
    
    Response:
        {
            "success": true,
            "message": "Database restored successfully",
            "uploaded_messages": 100,
            "final_messages": 100,
            "backup_path": "data/chat_history.db.backup.1234567890",
            "duration_seconds": 2.5,
            "restored_at": "2025-12-26T10:00:00"
        }
    """
    verify_api_key()
    
    # 檢查是否已在維護模式
    if db_service.is_maintenance:
        return jsonify({
            "error": "Database is already in maintenance mode",
            "reason": db_service.maintenance_reason
        }), 409
    
    # 檢查是否有上傳檔案
    if 'file' not in request.files:
        return jsonify({"error": "No file provided. Use 'file' field."}), 400
    
    uploaded_file = request.files['file']
    
    if uploaded_file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # 檢查檔案副檔名
    if not uploaded_file.filename.endswith('.db'):
        return jsonify({"error": "Invalid file type. Must be .db file"}), 400
    
    # 儲存到暫存檔案
    temp_file = None
    try:
        # 建立暫存檔案
        temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
        os.close(temp_fd)
        
        # 儲存上傳的檔案
        uploaded_file.save(temp_path)
        temp_file = temp_path
        
        print(f"[Restore API] File saved to temp: {temp_path}")
        print(f"[Restore API] File size: {os.path.getsize(temp_path)} bytes")
        
        # 執行還原
        result = db_service.restore_from_file(temp_path)
        
        # 清理舊備份（保留最近 3 個）
        db_service.cleanup_old_backups(keep_count=3)
        
        return jsonify(result)
        
    except DatabaseRestoreError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
    except Exception as e:
        # 確保解除維護模式
        if db_service.is_maintenance:
            db_service.set_maintenance(False)
        
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }), 500
        
    finally:
        # 清理暫存檔案（如果還存在）
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass


@app.route('/api/db/validate', methods=['POST'])
def validate_database_file():
    """
    驗證上傳的 SQLite 檔案（不進行還原）
    
    可用於在實際還原前先檢查檔案是否有效。
    """
    verify_api_key()
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    uploaded_file = request.files['file']
    
    temp_file = None
    try:
        # 儲存到暫存
        temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
        os.close(temp_fd)
        uploaded_file.save(temp_path)
        temp_file = temp_path
        
        # 驗證 SQLite header
        is_sqlite = db_service.validate_sqlite_file(temp_path)
        if not is_sqlite:
            return jsonify({
                "valid": False,
                "error": "Invalid SQLite file header"
            })
        
        # 驗證完整性
        is_valid, error_msg = db_service.validate_sqlite_integrity(temp_path)
        
        if is_valid:
            # 取得統計
            import sqlite3
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chat_messages")
            msg_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM chat_messages")
            user_count = cursor.fetchone()[0]
            conn.close()
            
            return jsonify({
                "valid": True,
                "message_count": msg_count,
                "user_count": user_count,
                "file_size_bytes": os.path.getsize(temp_path)
            })
        else:
            return jsonify({
                "valid": False,
                "error": error_msg
            })
            
    except Exception as e:
        return jsonify({
            "valid": False,
            "error": str(e)
        }), 500
        
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass


# ===== 啟動應用 =====

start_keepalive()

if __name__ == '__main__':
    app.run(debug=True)
