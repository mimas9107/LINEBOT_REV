"""
HackMD Plugin
版本: rev2.5.0
HackMD 筆記操作，提供 Gemini Function Calling 使用
"""

from services.hackmd_tools import (
    hackmd_list_notes,
    hackmd_read_note,
    hackmd_create_note,
    hackmd_update_note,
    hackmd_delete_note,
    hackmd_search_notes,
)

REQUIRED_ENV = ["HACKMD_API_TOKEN"]

TOOLS = [
    {
        "schema": {
            "name": "hackmd_list_notes",
            "description": "列出使用者的所有 HackMD 筆記，回傳精簡欄位（id、title、tags、createdAt）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "handler": hackmd_list_notes,
        "policy": {"risk": "READ_ONLY"},
    },
    {
        "schema": {
            "name": "hackmd_read_note",
            "description": "讀取單一 HackMD 筆記的內容（content 截斷至上限）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "筆記 ID"},
                },
                "required": ["note_id"],
            },
        },
        "handler": hackmd_read_note,
        "policy": {"risk": "READ_ONLY"},
    },
    {
        "schema": {
            "name": "hackmd_search_notes",
            "description": "搜尋 HackMD 筆記（依標題相關性排序；search_content=True 時也搜內文）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜尋關鍵字"},
                    "search_content": {"type": "boolean", "description": "是否同時搜尋內文（選填）"},
                    "fuzzy": {"type": "boolean", "description": "是否使用模糊（子序列）比對（選填）"},
                    "limit": {"type": "integer", "description": "最多回傳筆數，上限 100（選填）"},
                },
                "required": ["keyword"],
            },
        },
        "handler": hackmd_search_notes,
        "policy": {"risk": "READ_ONLY"},
    },
    {
        "schema": {
            "name": "hackmd_create_note",
            "description": "建立新的 HackMD 筆記。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "筆記標題"},
                    "content": {"type": "string", "description": "筆記內容（Markdown）"},
                    "read_permission": {"type": "string", "description": "讀取權限 owner/signed_in/guest（選填）"},
                    "write_permission": {"type": "string", "description": "寫入權限 owner/signed_in/guest（選填）"},
                },
                "required": ["title", "content"],
            },
        },
        "handler": hackmd_create_note,
        "policy": {"risk": "WRITE"},
    },
    {
        "schema": {
            "name": "hackmd_update_note",
            "description": "更新既有 HackMD 筆記的內容與權限。",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "筆記 ID"},
                    "content": {"type": "string", "description": "新的筆記內容（Markdown）"},
                    "read_permission": {"type": "string", "description": "讀取權限 owner/signed_in/guest（選填）"},
                    "write_permission": {"type": "string", "description": "寫入權限 owner/signed_in/guest（選填）"},
                },
                "required": ["note_id", "content"],
            },
        },
        "handler": hackmd_update_note,
        "policy": {"risk": "WRITE"},
    },
    {
        "schema": {
            "name": "hackmd_delete_note",
            "description": "刪除指定的 HackMD 筆記。此操作不可復原。",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "筆記 ID"},
                },
                "required": ["note_id"],
            },
        },
        "handler": hackmd_delete_note,
        "policy": {"risk": "DESTRUCTIVE"},
    },
]