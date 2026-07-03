---
name:          "MEMOIR.md"
description:   "Project architectural memory and decisions"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/07/03 10:21:24"
project_version: "2.2.0"
document_version: "1.1.0"
agent_sign: ['gemini cli/current_agent', 'codex/current_agent']
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
- **Deployment**: Complete deployment guide available in `DEPLOYMENT.md` covering Google Sheets/GAS setup, LINE Developer console, and Render.com.
