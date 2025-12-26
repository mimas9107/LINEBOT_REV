#!/usr/bin/env python3
"""
LINEBOT Database Analyzer Tool
版本: rev3

本地端工具，用於：
1. 從 Render.com 下載資料庫
2. 解析並輸出對話記錄
3. 匯出為各種格式 (JSON, CSV, TXT)

使用方式:
    python db_analyzer.py --help
    python db_analyzer.py download --url <URL> --api-key <KEY>
    python db_analyzer.py stats --db chat_history.db
    python db_analyzer.py export --db chat_history.db --format json
    python db_analyzer.py history --db chat_history.db --user <USER_ID>
"""

import argparse
import sqlite3
import json
import csv
import os
import sys
from datetime import datetime
from typing import Optional

# 嘗試匯入 requests，如果沒有則在下載時提示
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
        
        # 總訊息數
        cursor.execute("SELECT COUNT(*) FROM chat_messages")
        total_messages = cursor.fetchone()[0]
        
        # 使用者訊息數
        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE role = 'user'")
        user_messages = cursor.fetchone()[0]
        
        # AI 回應數
        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE role = 'model'")
        model_messages = cursor.fetchone()[0]
        
        # 不重複使用者數
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM chat_messages")
        unique_users = cursor.fetchone()[0]
        
        # 時間範圍
        cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM chat_messages")
        time_range = cursor.fetchone()
        
        # 檔案大小
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
        messages.reverse()  # 轉為時間正序
        
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
        
        print(f"Exported to: {output_path}")
    
    def export_csv(self, output_path: str, limit: int = 10000):
        """匯出為 CSV"""
        messages = self.get_messages(limit=limit)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if messages:
                writer = csv.DictWriter(f, fieldnames=messages[0].keys())
                writer.writeheader()
                writer.writerows(messages)
        
        print(f"Exported to: {output_path}")
    
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
        
        print(f"Exported to: {output_path}")


def download_database(url: str, api_key: str, output_path: str = "chat_history.db"):
    """從遠端下載資料庫"""
    if not HAS_REQUESTS:
        print("Error: 'requests' library is required. Install with: pip install requests")
        sys.exit(1)
    
    download_url = f"{url.rstrip('/')}/api/db/download"
    
    print(f"Downloading from: {download_url}")
    
    try:
        response = requests.get(
            download_url,
            headers={"X-API-Key": api_key},
            timeout=60
        )
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded to: {output_path}")
        print(f"File size: {len(response.content)} bytes")
        return output_path
        
    except requests.exceptions.RequestException as e:
        print(f"Error downloading database: {e}")
        sys.exit(1)


def print_stats(stats: dict):
    """印出統計資訊"""
    print("\n" + "=" * 50)
    print("DATABASE STATISTICS")
    print("=" * 50)
    print(f"Database Path:    {stats['database_path']}")
    print(f"File Size:        {stats['file_size_mb']} MB ({stats['file_size_bytes']} bytes)")
    print("-" * 50)
    print(f"Total Messages:   {stats['total_messages']}")
    print(f"  - User:         {stats['user_messages']}")
    print(f"  - AI:           {stats['model_messages']}")
    print(f"Unique Users:     {stats['unique_users']}")
    print("-" * 50)
    print(f"First Message:    {stats['first_message']}")
    print(f"Last Message:     {stats['last_message']}")
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
        
        # 截斷過長的文字
        if len(text) > 200:
            text = text[:200] + "..."
        
        print(f"\n[{time}] {role}:")
        print(f"  {text}")
    
    print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='LINEBOT Database Analyzer Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # 下載資料庫
  python db_analyzer.py download --url https://your-app.onrender.com --api-key YOUR_KEY

  # 查看統計
  python db_analyzer.py stats --db chat_history.db

  # 列出使用者
  python db_analyzer.py users --db chat_history.db

  # 查看特定使用者對話
  python db_analyzer.py history --db chat_history.db --user U1234567890

  # 匯出為 JSON
  python db_analyzer.py export --db chat_history.db --format json --output export.json

  # 匯出對話為文字檔
  python db_analyzer.py export --db chat_history.db --format txt --user U1234567890
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # download 指令
    download_parser = subparsers.add_parser('download', help='Download database from remote server')
    download_parser.add_argument('--url', required=True, help='Server URL (e.g., https://your-app.onrender.com)')
    download_parser.add_argument('--api-key', required=True, help='API secret key')
    download_parser.add_argument('--output', default='chat_history.db', help='Output file path')
    
    # stats 指令
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    stats_parser.add_argument('--db', required=True, help='Database file path')
    
    # users 指令
    users_parser = subparsers.add_parser('users', help='List all users')
    users_parser.add_argument('--db', required=True, help='Database file path')
    
    # history 指令
    history_parser = subparsers.add_parser('history', help='Show conversation history')
    history_parser.add_argument('--db', required=True, help='Database file path')
    history_parser.add_argument('--user', required=True, help='User ID')
    history_parser.add_argument('--limit', type=int, default=50, help='Number of messages')
    
    # export 指令
    export_parser = subparsers.add_parser('export', help='Export database')
    export_parser.add_argument('--db', required=True, help='Database file path')
    export_parser.add_argument('--format', choices=['json', 'csv', 'txt'], default='json', help='Export format')
    export_parser.add_argument('--output', help='Output file path')
    export_parser.add_argument('--user', help='User ID (required for txt format)')
    export_parser.add_argument('--limit', type=int, default=10000, help='Number of messages')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # 執行指令
    if args.command == 'download':
        download_database(args.url, args.api_key, args.output)
        
    elif args.command == 'stats':
        analyzer = DatabaseAnalyzer(args.db)
        stats = analyzer.get_stats()
        print_stats(stats)
        
    elif args.command == 'users':
        analyzer = DatabaseAnalyzer(args.db)
        users = analyzer.get_users()
        print_users(users)
        
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
                print("Error: --user is required for txt format")
                sys.exit(1)
            output = args.output or f'conversation_{args.user[:10]}.txt'
            analyzer.export_conversation_txt(args.user, output, args.limit)


if __name__ == '__main__':
    main()
