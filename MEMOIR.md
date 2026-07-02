---
name:          "MEMOIR.md"
description:   "Project architectural memory and decisions"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/07/02 10:00:00"
project_version: "2.1.0"
document_version: "1.0.1"
agent_sign: ['gemini cli/current_agent']
---

# Memoir

## Architectural Decisions
- **SDK Migration**: Migrated from `google-generativeai` to `google-genai` in version 2.0.0 for better performance and future-proofing.
- **Model Choice**: Standardized on `gemini-2.5-flash` for its multi-modal capabilities and performance. In 2.1.0, started using `gemini-flash-latest` alias.
- **State Management**: Using Google Sheets via Apps Script for persistent storage (bookmarks and history).
- **Environment Management**: Using `.env` for secrets and configuration.
- **Async Message Storage**: All `save_message` calls use `threading.Thread(daemon=True)` to prevent blocking the webhook handler.
- **Image Concurrency**: Image paths use `message_id` as filename to prevent concurrent overwrites, with automatic cleanup after analysis.
- **Bot History Persistence**: Bot replies are saved to Google Sheets with `userId="bot"` for multi-turn conversation context.
- **Deployment**: Complete deployment guide available in `DEPLOYMENT.md` covering Google Sheets/GAS setup, LINE Developer console, and Render.com.
