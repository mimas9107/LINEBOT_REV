"""
Log Context Module
版本: rev2.4.1
提供「目前正在處理的 LINE message id」的執行緒區域變數（threading.local）。

用途: 讓 handler 在處理每則 event 時設定 msgid，services 層（ai_text/ai_image）
擷取同一 msgid 加到每筆 log 前綴，即可用 `rg "msgid="` 追蹤單一訊息從
收到→模型重試→送出回覆的整條生命線。

threading.local 避免不同 request 之間互相污染（即便未來加多 thread worker 也安全）。
零簽名變更：此模組僅供 log 用，不需改變任何函式呼叫介面。
"""

import threading

_local = threading.local()


def set_msgid(msgid: str) -> None:
    """設定目前執行緒正在處理的 message id。"""
    _local.msgid = msgid


def get_msgid() -> str:
    """取得目前執行緒的 message id，無則回傳空字串。"""
    return getattr(_local, "msgid", "")


def prefix() -> str:
    """回傳 log 前綴片段，例如 `msgid=xxx `；無 msgid 時為空字串。"""
    m = get_msgid()
    return f"msgid={m} " if m else ""
