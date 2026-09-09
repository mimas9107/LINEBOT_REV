---
name:          "MEMOIR.md"
description:   "Project architectural memory and decisions"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/09/10 00:35:00"
project_version: "2.4.2"
document_version: "1.3.1"
agent_sign: ['gemini cli/current_agent', 'codex/current_agent', 'opencode/current_agent']
---

# Memoir

## Architectural Decisions
- **SDK Migration**: Migrated from `google-generativeai` to `google-genai` in version 2.0.0 for better performance and future-proofing.
- **Model Choice**: Standardized on `gemini-flash-latest` long-term alias to ensure automatic model migration while preserving multi-modal support.
- **State Management**: SQLite is the primary chat-history store for AI conversations. Google Sheets via Apps Script remains available for external logging/bookmarks and as a fallback history source.
- **Environment Management**: Using `.env` for secrets and configuration.
- **Async Message Storage**: All `save_message` calls use `threading.Thread(daemon=True)` to prevent blocking the webhook handler.
- **Image Concurrency**: Image paths use `message_id` as filename to prevent concurrent overwrites, with automatic cleanup after analysis.
- **Bot History Persistence**: Bot replies are saved to Google Sheets with `userId="bot"` for multi-turn conversation context.
- **SQLite Persistence**: User prompts, image events, AI replies, and image-analysis results are persisted to `data/chat_history.db`.
- **Database API Safety**: Read/download database APIs are authenticated by `API_SECRET_KEY`. Upload-based restore/validate endpoints are intentionally disabled on Render because the feature2 restore flow caused deployment instability.
- **Config Completeness**: `config.py` loads every supported runtime setting from environment variables and validates integer overrides for chat-history length and keepalive interval.
- **Keepalive Boot Safety**: `keepalive` now starts on the first incoming request; importing `app` under Gunicorn no longer starts the background thread during worker boot, while preserving runtime heartbeats after traffic begins.
- **Reminder System**: APScheduler `BackgroundScheduler` scans `reminders` table every `REMINDER_CHECK_INTERVAL` seconds. Due reminders are delivered via LINE `push_message` (not reply, because `reply_token` expires in 60 s). Each user is capped at `MAX_PENDING_REMINDERS = 20` pending reminders; sent/cancelled rows older than 7 days are auto-purged each cycle.
- **503 Resilience & History Sanitization**: `AITextService` fails loud (raises) and walks `config.MODEL_LIST` candidates with per-model 503/429 backoff retries (2 retries, `1.5s * attempt`); `markfail` models are skipped for 600 s after failure. Handlers persist only successful responses to SQLite/Sheets and reply a friendly message on failure, so error text never pollutes chat history.
- **Plugin Architecture**: `services/plugins/` loads tool modules gated by the `ENABLED_PLUGINS` whitelist (empty = no plugins) plus per-plugin `REQUIRED_ENV`; import/env failures skip with a warning, duplicate tool names raise at startup. Tool handlers are stateless, lazy-init clients, use 5–8 s HTTP timeouts, and return field-filtered JSON (never raw external API responses). The weather plugin (CWA rain PoP / GPS stations, TDX CCTV, route planning) was verified locally against live APIs before the 2.4.0 release.
- **Deployment**: Complete deployment guide available in `DEPLOYMENT.md` covering Google Sheets/GAS setup, LINE Developer console, and Render.com.
