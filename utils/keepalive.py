"""
Keepalive Utility Module
版本: rev3
處理背景保活任務，防止 Render.com 休眠
"""

import threading
import random
import time
import requests

from config import config
from services import log_keepalive


class KeepaliveManager:
    """保活任務管理器"""
    
    def __init__(self):
        self._thread = None
        self._running = False
    
    def start(self):
        """啟動保活背景執行緒"""
        if self._thread is not None and self._thread.is_alive():
            print("[Keepalive] Already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._activity_loop, daemon=True)
        self._thread.start()
        print("[Keepalive] Started")
    
    def stop(self):
        """停止保活背景執行緒"""
        self._running = False
        print("[Keepalive] Stopped")
    
    def _activity_loop(self):
        """保活任務主迴圈"""
        tasks = [
            self._ping_self,
            self._ping_external,
            self._log_to_sheet
        ]
        
        while self._running:
            # 隨機挑選一項任務執行
            task = random.choice(tasks)
            task_name = task.__name__
            
            print(f"[Keepalive] Executing: {task_name}")
            
            try:
                task()
            except Exception as e:
                print(f"[Keepalive] Error in {task_name}: {e}")
            
            # 等待指定間隔
            time.sleep(config.KEEPALIVE_INTERVAL)
    
    def _ping_self(self):
        """Ping 自己的服務"""
        try:
            print("[Keepalive] Pinging self /about")
            response = requests.get(config.SELF_URL, timeout=30)
            print(f"[Keepalive] Self ping status: {response.status_code}")
        except Exception as e:
            print(f"[Keepalive] Self ping error: {e}")
    
    def _ping_external(self):
        """Ping 外部 API"""
        try:
            print("[Keepalive] Pinging external API")
            response = requests.get("https://wttr.in/Taipei?format=3", timeout=30)
            print(f"[Keepalive] External response: {response.text.strip()}")
        except Exception as e:
            print(f"[Keepalive] External ping error: {e}")
    
    def _log_to_sheet(self):
        """記錄到 Google Sheet"""
        try:
            print("[Keepalive] Logging to Google Sheet")
            log_keepalive(
                function_name="keepalive_log",
                status="OK",
                note="系統保持清醒記錄"
            )
        except Exception as e:
            print(f"[Keepalive] Sheet log error: {e}")


# 建立全域管理器實例
keepalive_manager = KeepaliveManager()


def start_keepalive():
    """便捷函式：啟動保活任務"""
    keepalive_manager.start()


def stop_keepalive():
    """便捷函式：停止保活任務"""
    keepalive_manager.stop()
