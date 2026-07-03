"""
Reminder Service Module
排程提醒服務 (APScheduler + SQLite)
"""

import re
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
)

from config import config
from services.database import db_service


class ReminderService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self._started = False

    def start(self):
        if self._started:
            return
        self.scheduler.add_job(
            self._check_reminders, 'interval',
            seconds=config.REMINDER_CHECK_INTERVAL,
            id='check_reminders', replace_existing=True,
        )
        self.scheduler.start()
        self._started = True
        print("[Reminder] Scheduler started")

    def stop(self):
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            print("[Reminder] Scheduler stopped")

    def _check_reminders(self):
        try:
            rows = db_service.execute(
                "SELECT * FROM reminders WHERE status='pending' AND remind_at <= datetime('now', 'localtime')"
            )
            for r in rows:
                self._push(r)
                db_service.execute_write(
                    "UPDATE reminders SET status='sent', notified_at=datetime('now', 'localtime') WHERE id=?",
                    (r['id'],)
                )
            db_service.execute_write(
                "DELETE FROM reminders WHERE status IN ('sent', 'cancelled') AND created_at < datetime('now', 'localtime', '-7 days')"
            )
        except Exception as e:
            print(f"[Reminder] Check error: {e}")

    def _push(self, reminder):
        try:
            conf = Configuration(access_token=config.LINE_CHANNEL_ACCESS_TOKEN)
            with ApiClient(conf) as api_client:
                MessagingApi(api_client).push_message(
                    PushMessageRequest(
                        to=reminder['user_id'],
                        messages=[TextMessage(text=f"⏰ 提醒：{reminder['message']}")]
                    )
                )
        except Exception as e:
            print(f"[Reminder] Push error for id={reminder['id']}: {e}")

    # ponytail: SQLite datetime() 不認 isoformat 的 T 跟微秒，用 strftime 對齊格式
    def create(self, user_id, remind_at, message):
        return db_service.execute_insert(
            "INSERT INTO reminders (user_id, remind_at, message) VALUES (?, ?, ?)",
            (user_id, remind_at.strftime('%Y-%m-%d %H:%M:%S'), message)
        )

    def list_pending(self, user_id):
        return db_service.execute(
            "SELECT id, message, remind_at, created_at FROM reminders WHERE user_id=? AND status='pending' ORDER BY remind_at",
            (user_id,)
        )

    def cancel(self, reminder_id, user_id):
        n = db_service.execute_write(
            "UPDATE reminders SET status='cancelled' WHERE id=? AND user_id=? AND status='pending'",
            (reminder_id, user_id)
        )
        return n > 0


reminder_service = ReminderService()


# ---- 文字解析 ----

def parse_remind_time(text):
    now = datetime.now()
    patterns = [
        (r'(\d+)\s*分鐘後', lambda m: timedelta(minutes=int(m.group(1)))),
        (r'(\d+)\s*分後',    lambda m: timedelta(minutes=int(m.group(1)))),
        (r'(\d+)\s*小時後',  lambda m: timedelta(hours=int(m.group(1)))),
        (r'(\d+)\s*天後',    lambda m: timedelta(days=int(m.group(1)))),
        (r'(\d+)\s*秒後',    lambda m: timedelta(seconds=int(m.group(1)))),
    ]
    for pat, fn in patterns:
        m = re.search(pat, text)
        if m:
            return now + fn(m)
    return None


def create_reminder(user_id, text):
    cleaned = re.sub(r'^ai:\s*', '', text, flags=re.IGNORECASE).strip()
    m = re.search(r'(\d+\s*(分鐘|分|小時|天|秒)後)', cleaned)
    if not m:
        return False, "無法解析時間，目前支援：X分鐘後 / X小時後 / X天後"

    pending = db_service.execute(
        "SELECT COUNT(*) as cnt FROM reminders WHERE user_id=? AND status='pending'",
        (user_id,)
    )[0]['cnt']
    if pending >= config.MAX_PENDING_REMINDERS:
        return False, f"⚠️ 待處理提醒已達上限 ({config.MAX_PENDING_REMINDERS} 筆)，請先取消或等待既有提醒執行"

    remind_at = parse_remind_time(m.group(1))
    parts = cleaned.split(m.group(1))
    message = ''.join(parts).strip()
    message = re.sub(r'^(提醒我|remind me\s*(to\s+|in\s+|of\s+)?)', '', message, flags=re.IGNORECASE)
    message = re.sub(r'\s+', ' ', message).strip()
    while True:
        cleaned = re.sub(r'^(to|in|after|at|before)\s+', '', message, flags=re.IGNORECASE).strip()
        if cleaned == message:
            break
        message = cleaned
    message = re.sub(r'\s+(in|after|at|before)\s*$', '', message, flags=re.IGNORECASE).strip()
    if not message:
        return False, "請告訴我要提醒什麼"

    reminder_service.create(user_id, remind_at, message)
    return True, f"✅ 已設定提醒「{message}」⏰ {remind_at.strftime('%m/%d %H:%M')}"


def handle_reminder_command(user_id, text):
    text = text.strip()

    if text.startswith('取消提醒') or re.match(r'取消\s*#?\d+', text):
        m = re.search(r'#?(\d+)', text)
        if not m:
            return "格式：取消提醒 #[id]"
        ok = reminder_service.cancel(int(m.group(1)), user_id)
        return f"✅ 已取消提醒 #{m.group(1)}" if ok else "❌ 找不到該提醒或已非待處理"

    if text in ('提醒列表', '我的提醒', '提醒清單', 'list reminders'):
        rows = reminder_service.list_pending(user_id)
        if not rows:
            return "📭 目前沒有待處理的提醒"
        lines = ["📋 待處理提醒："]
        for r in rows:
            lines.append(f"  #{r['id']} ⏰ {r['remind_at']} 📝 {r['message']}")
        lines.append("取消請輸入：取消提醒 #[id]")
        return '\n'.join(lines)

    success, msg = create_reminder(user_id, text)
    return msg
