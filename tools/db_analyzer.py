#!/usr/bin/env python3
"""
LINEBOT Database Analyzer Tool
版本: rev3.1

本地端工具，用於：
1. 從 Render.com 下載資料庫
2. 解析並輸出對話記錄
3. 匯出為各種格式 (JSON, CSV, TXT)
4. 【新增】還原資料庫到遠端伺服器

使用方式:
    python db_analyzer.py --help
    python db_analyzer.py download --url <URL> --api-key <KEY>
    python db_analyzer.py restore --url <URL> --api-key <KEY> --file <DB_FILE>
    python db_analyzer.py stats --db chat_history.db
    python db_analyzer.py export --db chat_history.db --format json
"""

import argparse
import sqlite3
import json
import csv
import os
import sys
from datetime import datetime
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class DatabaseAnalyzer:
    """資料庫分析器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")
    
    def get_connection(self):
        """取得資料庫連線"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_stats(self) -> dict:
        """取得統計資訊"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM chat_messages")
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE role = 'user'")
        user_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE role = 'model'")
        model_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM chat_messages")
        unique_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM chat_messages")
        time_range = cursor.fetchone()
        
        file_size = os.path.getsize(self.db_path)
        conn.close()
        
        return {
            "database_path": self.db_path,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / 1024 / 1024, 2),
            "total_messages": total_messages,
            "user_messages": user_messages,
            "model_messages": model_messages,
            "unique_users": unique_users,
            "first_message": time_range[0],
            "last_message": time_range[1]
        }
    
    def get_users(self) -> list:
        """取得所有使用者統計"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                user_id,
                COUNT(*) as total_messages,
                SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) as user_msgs,
                SUM(CASE WHEN role = 'model' THEN 1 ELSE 0 END) as model_msgs,
                MIN(created_at) as first_message,
                MAX(created_at) as last_message
            FROM chat_messages
            GROUP BY user_id
            ORDER BY last_message DESC
        ''')
        
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    
    def get_messages(self, limit: int = 100, offset: int = 0, user_id: str = None) -> list:
        """取得訊息列表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT id, user_id, role, message_type, message_text, created_at
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))
        else:
            cursor.execute('''
                SELECT id, user_id, role, message_type, message_text, created_at
                FROM chat_messages
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages
    
    def get_conversation(self, user_id: str, limit: int = 50) -> list:
        """取得特定使用者的對話（時間正序）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT role, message_type, message_text, created_at
            FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        messages = [dict(row) for row in cursor.fetchall()]
        messages.reverse()
        
        conn.close()
        return messages
    
    def export_json(self, output_path: str, limit: int = 10000):
        """匯出為 JSON"""
        data = {
            "export_time": datetime.now().isoformat(),
            "stats": self.get_stats(),
            "users": self.get_users(),
            "messages": self.get_messages(limit=limit)
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Exported to: {output_path}")
    
    def export_csv(self, output_path: str, limit: int = 10000):
        """匯出為 CSV"""
        messages = self.get_messages(limit=limit)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if messages:
                writer = csv.DictWriter(f, fieldnames=messages[0].keys())
                writer.writeheader()
                writer.writerows(messages)
        
        print(f"✅ Exported to: {output_path}")
    
    def export_conversation_txt(self, user_id: str, output_path: str, limit: int = 100):
        """匯出對話為易讀文字格式"""
        messages = self.get_conversation(user_id, limit)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"=== Conversation with {user_id[:15]}... ===\n")
            f.write(f"Export time: {datetime.now().isoformat()}\n")
            f.write(f"Messages: {len(messages)}\n")
            f.write("=" * 50 + "\n\n")
            
            for msg in messages:
                role = "User" if msg['role'] == 'user' else "AI"
                time = msg['created_at']
                text = msg['message_text'] or "[empty]"
                
                f.write(f"[{time}] {role}:\n")
                f.write(f"{text}\n")
                f.write("-" * 30 + "\n")
        
        print(f"✅ Exported to: {output_path}")


# ===== 遠端 API 操作 =====

def check_requests():
    """檢查 requests 是否安裝"""
    if not HAS_REQUESTS:
        print("❌ Error: 'requests' library is required.")
        print("   Install with: pip install requests")
        sys.exit(1)


def download_database(url: str, api_key: str, output_path: str = "chat_history.db"):
    """從遠端下載資料庫"""
    check_requests()
    
    download_url = f"{url.rstrip('/')}/api/db/download"
    
    print(f"📥 Downloading from: {download_url}")
    
    try:
        response = requests.get(
            download_url,
            headers={"X-API-Key": api_key},
            timeout=60
        )
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ Downloaded to: {output_path}")
        print(f"   File size: {len(response.content):,} bytes")
        
        # 顯示統計
        try:
            analyzer = DatabaseAnalyzer(output_path)
            stats = analyzer.get_stats()
            print(f"   Messages: {stats['total_messages']}")
            print(f"   Users: {stats['unique_users']}")
        except:
            pass
        
        return output_path
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error downloading database: {e}")
        sys.exit(1)


def restore_database(url: str, api_key: str, db_file: str, validate_only: bool = False):
    """
    還原資料庫到遠端伺服器
    
    Args:
        url: 伺服器 URL
        api_key: API 金鑰
        db_file: 本地 SQLite 檔案路徑
        validate_only: 僅驗證，不實際還原
    """
    check_requests()
    
    if not os.path.exists(db_file):
        print(f"❌ Error: File not found: {db_file}")
        sys.exit(1)
    
    file_size = os.path.getsize(db_file)
    print(f"📁 File: {db_file}")
    print(f"   Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    
    # 本地驗證
    print("\n🔍 Local validation...")
    try:
        analyzer = DatabaseAnalyzer(db_file)
        stats = analyzer.get_stats()
        print(f"   ✅ Valid SQLite file")
        print(f"   Messages: {stats['total_messages']}")
        print(f"   Users: {stats['unique_users']}")
    except Exception as e:
        print(f"   ❌ Invalid file: {e}")
        sys.exit(1)
    
    # 遠端驗證
    if validate_only:
        endpoint = f"{url.rstrip('/')}/api/db/validate"
        action_name = "Validating"
    else:
        endpoint = f"{url.rstrip('/')}/api/db/restore"
        action_name = "Restoring"
    
    print(f"\n📤 {action_name} to: {endpoint}")
    
    # 確認提示（僅在實際還原時）
    if not validate_only:
        print("\n⚠️  WARNING: This will replace the remote database!")
        print("   The server will enter maintenance mode during restore.")
        confirm = input("   Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Cancelled")
            sys.exit(0)
    
    try:
        with open(db_file, 'rb') as f:
            files = {'file': (os.path.basename(db_file), f, 'application/x-sqlite3')}
            response = requests.post(
                endpoint,
                headers={"X-API-Key": api_key},
                files=files,
                timeout=120
            )
        
        result = response.json()
        
        if response.status_code == 200:
            if validate_only:
                print("\n✅ Remote validation passed:")
                print(f"   Messages: {result.get('message_count', 'N/A')}")
                print(f"   Users: {result.get('user_count', 'N/A')}")
            else:
                print("\n✅ Restore successful!")
                print(f"   Messages restored: {result.get('final_messages', 'N/A')}")
                print(f"   Duration: {result.get('duration_seconds', 'N/A')}s")
                print(f"   Backup: {result.get('backup_path', 'N/A')}")
        else:
            print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request error: {e}")
        sys.exit(1)


def get_remote_stats(url: str, api_key: str):
    """取得遠端伺服器的資料庫統計"""
    check_requests()
    
    stats_url = f"{url.rstrip('/')}/api/db/stats"
    
    try:
        response = requests.get(
            stats_url,
            headers={"X-API-Key": api_key},
            timeout=30
        )
        response.raise_for_status()
        
        stats = response.json()
        print_stats(stats, title="REMOTE DATABASE STATISTICS")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def get_maintenance_status(url: str, api_key: str):
    """取得維護模式狀態"""
    check_requests()
    
    status_url = f"{url.rstrip('/')}/api/db/maintenance"
    
    try:
        response = requests.get(
            status_url,
            headers={"X-API-Key": api_key},
            timeout=30
        )
        response.raise_for_status()
        
        status = response.json()
        
        if status.get('maintenance_mode'):
            print(f"🔧 Maintenance mode: ENABLED")
            print(f"   Reason: {status.get('reason', 'N/A')}")
        else:
            print(f"✅ Maintenance mode: DISABLED")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


# ===== 輸出格式化 =====

def print_stats(stats: dict, title: str = "DATABASE STATISTICS"):
    """印出統計資訊"""
    print("\n" + "=" * 50)
    print(title)
    print("=" * 50)
    
    for key, value in stats.items():
        # 格式化 key
        display_key = key.replace('_', ' ').title()
        print(f"{display_key}: {value}")
    
    print("=" * 50 + "\n")


def print_users(users: list):
    """印出使用者列表"""
    print("\n" + "=" * 80)
    print("USER LIST")
    print("=" * 80)
    print(f"{'User ID':<40} {'Total':>8} {'User':>8} {'AI':>8} {'Last Active':<20}")
    print("-" * 80)
    
    for user in users:
        user_id = user['user_id'][:38] + '..' if len(user['user_id']) > 40 else user['user_id']
        print(f"{user_id:<40} {user['total_messages']:>8} {user['user_msgs']:>8} {user['model_msgs']:>8} {user['last_message'] or 'N/A':<20}")
    
    print("=" * 80 + "\n")


def print_conversation(messages: list, user_id: str):
    """印出對話內容"""
    print("\n" + "=" * 60)
    print(f"CONVERSATION: {user_id[:30]}...")
    print("=" * 60)
    
    for msg in messages:
        role = "👤 User" if msg['role'] == 'user' else "🤖 AI"
        time = msg['created_at']
        text = msg['message_text'] or "[empty]"
        
        if len(text) > 200:
            text = text[:200] + "..."
        
        print(f"\n[{time}] {role}:")
        print(f"  {text}")
    
    print("\n" + "=" * 60 + "\n")


# ===== 主程式 =====

def main():
    parser = argparse.ArgumentParser(
        description='LINEBOT Database Analyzer Tool (rev3.1)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # 下載資料庫
  python db_analyzer.py download --url https://your-app.onrender.com --api-key YOUR_KEY

  # 還原資料庫（上傳本地 DB 到遠端）
  python db_analyzer.py restore --url https://your-app.onrender.com --api-key YOUR_KEY --file backup.db

  # 僅驗證檔案（不實際還原）
  python db_analyzer.py validate --url https://your-app.onrender.com --api-key YOUR_KEY --file backup.db

  # 查看遠端狀態
  python db_analyzer.py remote-stats --url https://your-app.onrender.com --api-key YOUR_KEY
  python db_analyzer.py maintenance --url https://your-app.onrender.com --api-key YOUR_KEY

  # 本地分析
  python db_analyzer.py stats --db chat_history.db
  python db_analyzer.py users --db chat_history.db
  python db_analyzer.py history --db chat_history.db --user U1234567890

  # 匯出
  python db_analyzer.py export --db chat_history.db --format json --output export.json
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # download
    dl_parser = subparsers.add_parser('download', help='Download database from remote')
    dl_parser.add_argument('--url', required=True, help='Server URL')
    dl_parser.add_argument('--api-key', required=True, help='API key')
    dl_parser.add_argument('--output', default='chat_history.db', help='Output file')
    
    # restore (新增)
    rs_parser = subparsers.add_parser('restore', help='Restore database to remote server')
    rs_parser.add_argument('--url', required=True, help='Server URL')
    rs_parser.add_argument('--api-key', required=True, help='API key')
    rs_parser.add_argument('--file', required=True, help='Local SQLite file to upload')
    
    # validate (新增)
    vl_parser = subparsers.add_parser('validate', help='Validate database file on remote (no restore)')
    vl_parser.add_argument('--url', required=True, help='Server URL')
    vl_parser.add_argument('--api-key', required=True, help='API key')
    vl_parser.add_argument('--file', required=True, help='Local SQLite file to validate')
    
    # remote-stats (新增)
    rstat_parser = subparsers.add_parser('remote-stats', help='Get remote database statistics')
    rstat_parser.add_argument('--url', required=True, help='Server URL')
    rstat_parser.add_argument('--api-key', required=True, help='API key')
    
    # maintenance (新增)
    maint_parser = subparsers.add_parser('maintenance', help='Check maintenance mode status')
    maint_parser.add_argument('--url', required=True, help='Server URL')
    maint_parser.add_argument('--api-key', required=True, help='API key')
    
    # stats (本地)
    stats_parser = subparsers.add_parser('stats', help='Show local database statistics')
    stats_parser.add_argument('--db', required=True, help='Database file path')
    
    # users (本地)
    users_parser = subparsers.add_parser('users', help='List all users')
    users_parser.add_argument('--db', required=True, help='Database file path')
    
    # history (本地)
    hist_parser = subparsers.add_parser('history', help='Show conversation history')
    hist_parser.add_argument('--db', required=True, help='Database file path')
    hist_parser.add_argument('--user', required=True, help='User ID')
    hist_parser.add_argument('--limit', type=int, default=50, help='Number of messages')
    
    # export (本地)
    exp_parser = subparsers.add_parser('export', help='Export database')
    exp_parser.add_argument('--db', required=True, help='Database file path')
    exp_parser.add_argument('--format', choices=['json', 'csv', 'txt'], default='json')
    exp_parser.add_argument('--output', help='Output file path')
    exp_parser.add_argument('--user', help='User ID (required for txt format)')
    exp_parser.add_argument('--limit', type=int, default=10000, help='Number of messages')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 執行指令
    if args.command == 'download':
        download_database(args.url, args.api_key, args.output)
        
    elif args.command == 'restore':
        restore_database(args.url, args.api_key, args.file, validate_only=False)
        
    elif args.command == 'validate':
        restore_database(args.url, args.api_key, args.file, validate_only=True)
        
    elif args.command == 'remote-stats':
        get_remote_stats(args.url, args.api_key)
        
    elif args.command == 'maintenance':
        get_maintenance_status(args.url, args.api_key)
        
    elif args.command == 'stats':
        analyzer = DatabaseAnalyzer(args.db)
        print_stats(analyzer.get_stats())
        
    elif args.command == 'users':
        analyzer = DatabaseAnalyzer(args.db)
        print_users(analyzer.get_users())
        
    elif args.command == 'history':
        analyzer = DatabaseAnalyzer(args.db)
        messages = analyzer.get_conversation(args.user, args.limit)
        print_conversation(messages, args.user)
        
    elif args.command == 'export':
        analyzer = DatabaseAnalyzer(args.db)
        
        if args.format == 'json':
            output = args.output or 'export.json'
            analyzer.export_json(output, args.limit)
            
        elif args.format == 'csv':
            output = args.output or 'export.csv'
            analyzer.export_csv(output, args.limit)
            
        elif args.format == 'txt':
            if not args.user:
                print("❌ Error: --user is required for txt format")
                sys.exit(1)
            output = args.output or f'conversation_{args.user[:10]}.txt'
            analyzer.export_conversation_txt(args.user, output, args.limit)


if __name__ == '__main__':
    main()
