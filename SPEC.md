---
name:          "SPEC.md"
description:   "Project specifications and requirements"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/09/23 10:00:00"
project_version: "2.6.0"
document_version: "1.4.0"
agent_sign: ['gemini cli/current_agent', 'codex/current_agent', 'opencode/current_agent']
---

# Specifications

## Core Features
- LINE Bot integration via Webhook.
- Gemini AI integration for text and image analysis.
- Multi-turn conversation support.
- Bookmark and history storage in Google Sheets.
- SQLite-backed conversation persistence.
- Authenticated database read/download API.
- Disabled database upload/restore endpoints for Render deployment safety.
- Keepalive starts on the first incoming request, not on worker import.
- Keep-alive mechanism to prevent service sleep.
- Gemini text fallback via `MODEL_LIST`: 503/429 retry with exponential backoff and markfail cooldown; failed AI calls are never persisted to chat history.
- Plugin system for Gemini Function Calling: `services/plugins/` modules enabled via the `ENABLED_PLUGINS` whitelist; duplicate tool names fail startup, non-callable handlers are skipped; missing `REQUIRED_ENV` skips the plugin. Each tool may declare a risk policy (`READ_ONLY` / `WRITE` / `DESTRUCTIVE`, default `READ_ONLY`); WRITE/DESTRUCTIVE tools are checked against the caller-identity allow-list before execution, and group/room identities are restricted to `READ_ONLY`. Tool results are field-filtered and the tool-loop caps apply (3 rounds / 6 calls / 25 s). SPEC records only mechanisms; per-plugin tool inventory and permissions live in the plugin modules and README.

## Tech Stack
- Python 3.x
- Flask
- google-genai SDK
- Line Bot SDK
- Google Apps Script
- SQLite

## Versioning Policy
- Mainline releases on `main` use an even MAJOR version number.
- Feature or experimental branches use an odd MAJOR version number.
- MINOR and PATCH versions increment normally within each branch line.
- This policy is effective starting with the feature2-to-main merge that produced `2.2.0`.
- Example: `2.x.y` is a mainline release series; `3.x.y` is a feature/testing series.

## Database API
- All database API routes require `API_SECRET_KEY`.
- If `API_SECRET_KEY` is unset, database API routes return `503`.
- `GET /api/db/download` downloads the SQLite database file.
- `GET /api/db/stats` returns database statistics.
- `GET /api/db/export` exports chat history as JSON.
- `GET /api/db/messages` queries messages.
- `GET /api/db/users` returns user statistics.
- `GET /api/db/user/<user_id>/history` returns one user's history.
- `POST /api/db/restore` and `POST /api/db/validate` must remain disabled until a safer restore strategy is implemented.
