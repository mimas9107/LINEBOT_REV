"""
HackMD Tools Module
版本: rev2.5.0
6 支 stateless handler，提供 HackMD 筆記操作給 Gemini Function Calling

更新紀錄:
- rev2.5.0: 新增 HackMD 插件工具層（list/read/create/update/delete/search）
"""

import json
import os
import re
import time

import requests

DEFAULT_TIMEOUT = 8.0
HACKMD_API_URL = "https://api.hackmd.io/v1"
MAX_CONTENT_CHARS = 2000
NOTES_CACHE_TTL = 60.0
MAX_CONTENT_SCAN = 20  # search_content=True 時最多逐筆讀取幾則內容，避免過多呼叫

_client = None
_notes_cache: list = []
_notes_cache_ts = 0.0


def _get_client() -> requests.Session:
    """lazy init：模組頂層不建立 client。"""
    global _client
    if _client is None:
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {os.getenv('HACKMD_API_TOKEN', '')}",
        })
        _client = session
    return _client


def _sanitize_error(e: Exception) -> str:
    """清洗例外訊息，避免帶出 Authorization / token。"""
    msg = str(e)
    return re.sub(r"(?i)(authorization=)[^&\"'\s]+", r"\1***", msg)


def _invalidate_notes_cache() -> None:
    global _notes_cache, _notes_cache_ts
    _notes_cache = []
    _notes_cache_ts = 0.0


def _get_notes_cached():
    """回傳 (ok, notes|error)。寫入類操作後拆快取失效。"""
    global _notes_cache, _notes_cache_ts
    now = time.time()
    if _notes_cache and now - _notes_cache_ts < NOTES_CACHE_TTL:
        return True, _notes_cache
    try:
        resp = _get_client().get(f"{HACKMD_API_URL}/notes", timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return False, {"error": "Unexpected response format from HackMD"}
    except Exception as e:
        return False, {"error": _sanitize_error(e)}
    _notes_cache = data
    _notes_cache_ts = now
    return True, _notes_cache


def _filter_list_note(note: dict) -> dict:
    return {
        "id": note.get("id"),
        "title": note.get("title", ""),
        "tags": note.get("tags", []),
        "createdAt": note.get("createdAt"),
    }


def _filter_read_note(note: dict) -> dict:
    content = note.get("content", "")
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n…(truncated)"
    return {"id": note.get("id"), "title": note.get("title", ""), "content": content}


def hackmd_list_notes():
    """列出所有筆記。"""
    ok, data = _get_notes_cached()
    if not ok:
        return data
    return [_filter_list_note(n) for n in data]


def hackmd_read_note(note_id):
    """讀取單一筆記內容。"""
    if not note_id:
        return {"error": "note_id is required"}
    try:
        resp = _get_client().get(
            f"{HACKMD_API_URL}/notes/{note_id}", timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        note = resp.json()
    except Exception as e:
        return {"error": _sanitize_error(e)}
    return _filter_read_note(note)


def hackmd_create_note(title, content, read_permission=None, write_permission=None):
    """建立新筆記。"""
    if not title:
        return {"error": "title is required"}
    if not content:
        return {"error": "content is required"}
    payload = {"title": title, "content": content}
    if read_permission:
        payload["readPermission"] = read_permission
    if write_permission:
        payload["writePermission"] = write_permission
    try:
        resp = _get_client().post(
            f"{HACKMD_API_URL}/notes", json=payload, timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        note_id = resp.json().get("id")
    except Exception as e:
        return {"error": _sanitize_error(e)}
    _invalidate_notes_cache()
    return {"id": note_id, "title": title}


def hackmd_update_note(note_id, content, read_permission=None, write_permission=None):
    """更新既有筆記。"""
    if not note_id:
        return {"error": "note_id is required"}
    if not content:
        return {"error": "content is required"}
    payload = {"content": content}
    if read_permission:
        payload["readPermission"] = read_permission
    if write_permission:
        payload["writePermission"] = write_permission
    try:
        resp = _get_client().patch(
            f"{HACKMD_API_URL}/notes/{note_id}", json=payload, timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        body = resp.text
        note = json.loads(body) if body.strip() else {}
    except Exception as e:
        return {"error": _sanitize_error(e)}
    _invalidate_notes_cache()
    return {"id": note.get("id") or note_id, "title": note.get("title", "")}


def hackmd_delete_note(note_id):
    """刪除筆記。"""
    if not note_id:
        return {"error": "note_id is required"}
    try:
        resp = _get_client().delete(
            f"{HACKMD_API_URL}/notes/{note_id}", timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
    except Exception as e:
        return {"error": _sanitize_error(e)}
    _invalidate_notes_cache()
    return {"success": True, "id": note_id}


def _title_score(title: str, keyword: str) -> int:
    """標題相關性分數：完整匹配 > 開頭 > 包含 > 字詞。回傳 0 表示無關。"""
    tl = title.lower()
    kw = keyword.lower()
    if tl == kw:
        return 6
    if tl.startswith(kw):
        return 5
    if kw in tl:
        return 4
    kwords = [w for w in kw.split() if w]
    if kwords and all(kw != "" for kw in kwords):
        overlap = sum(1 for w in kwords if w in tl.split())
        if overlap:
            return 2 + overlap
    return 0


def _fuzzy_match(keyword: str, text: str) -> bool:
    """子序列模糊匹配：keyword 字元依序出現在 text 中。"""
    idx = 0
    for ch in keyword.lower():
        idx = text.lower().find(ch, idx)
        if idx == -1:
            return False
        idx += 1
    return True


def hackmd_search_notes(keyword, search_content=False, fuzzy=False, limit=20):
    """以本地相關性搜尋筆記。"""
    if not keyword:
        return {"error": "keyword is required"}
    try:
        limit = min(max(int(limit), 1), 100)
    except (TypeError, ValueError):
        limit = 20
    ok, notes = _get_notes_cached()
    if not ok:
        return notes

    scored = []
    for note in notes:
        title = note.get("title", "")
        score = _title_score(title, keyword)
        if score == 0 and fuzzy:
            score = 1 if _fuzzy_match(keyword, title) else 0
        if score > 0:
            scored.append({"note": note, "score": score})

    if search_content:
        known_ids = {s["note"].get("id") for s in scored}
        scanned = 0
        for note in notes:
            if scanned >= MAX_CONTENT_SCAN:
                break
            if note.get("id") in known_ids:
                continue
            scanned += 1
            full = hackmd_read_note(note.get("id"))
            if isinstance(full, dict) and full.get("id") and keyword.lower() in full.get("content", "").lower():
                scored.append({"note": note, "score": 1})

    scored.sort(key=lambda s: s["score"], reverse=True)
    return [
        {"id": n.get("id"), "title": n.get("title", ""),
         "_meta": {"score": s["score"]}}
        for n, s in ((s["note"], s) for s in scored[:limit])
    ]


if __name__ == "__main__":
    # ponytail: 最小自我檢查 — 只驗證本地邏輯（欄位篩選/相關性），不碰外部 API
    assert _title_score("今天天氣", "今天天氣") == 6
    assert _title_score("今天天氣", "今天") == 5
    assert _title_score("今天天氣真好", "天氣") == 4
    assert _title_score("今天天氣", "颱風") == 0
    assert _fuzzy_match("abc", "aXbYcZ")
    assert not _fuzzy_match("axc", "abc")
    assert _filter_list_note({"id": "1", "title": "t", "tags": ["a"], "createdAt": 5}) == {
        "id": "1", "title": "t", "tags": ["a"], "createdAt": 5}
    long_content = "x" * 3000
    filtered = _filter_read_note({"id": "1", "title": "t", "content": long_content})
    assert len(filtered["content"]) == MAX_CONTENT_CHARS + len("\n…(truncated)")
    assert "truncated" in filtered["content"]
    print("hackmd_tools self-check OK")