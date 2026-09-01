---
name:          "CHANGELOG.md"
description:   "Project change history"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/09/01 10:49:03"
project_version: "2.3.2"
document_version: "1.4.0"
agent_sign: ['gemini cli/current_agent', 'codex/current_agent', 'opencode/current_agent']
---

# Changelog

## [2.3.2] - 2026-09-01
### Changed
- `max_output_tokens` reduced 8192 -> 4096 (both `chat()` and `_chat_with_history`) to cut Gemini latency and reduce gunicorn worker timeout pressure.
- `AITextService._generate` now logs the active model on successful response: `[AITextService] current model=<model> -> OK`, alongside existing per-attempt failure/skip logs, so Render logs show which candidate actually served a reply.
- Runtime resilience verified live on Render (livelog3): `gemini-flash-latest` hit 503 x3, was markfailed, then fell back to the next `MODEL_LIST` candidate and replied successfully across consecutive `ai:` messages; markfail cooldown (600 s) skipped the failed model on subsequent requests.
- Deployment: Render Start Command raised gunicorn timeout to 300 s (`gunicorn app:app --timeout 300`) to stop workers from being SIGKILLed while waiting on slow Gemini responses (observed 30 s default timeout killing the worker mid-request).
### Notes
- Patch release on `main`, following the even-MAJOR versioning policy.

## [2.3.1] - 2026-09-01
### Fixed
- AI text failures no longer swallow exceptions into error strings (`AITextService.chat` / `generate_simple` now raise), preventing `503 UNAVAILABLE` messages from being saved as model responses.
- `LineHandler` skips SQLite/Google Sheet writes when AI text or image analysis fails, replying a friendly message instead (chat-history anti-pollution).
- Image analysis (`AIImageService`) now raises on failure instead of returning error strings.

### Added
- `MODEL_LIST` fallback chain in `config.py`: `gemini-flash-latest` (markfail) -> `gemini-2.5-flash` -> `gemini-1.5-flash` -> `gemini-1.5-pro`.
- 503/429 exponential-backoff retry (2 retries, `1.5s * attempt`), markfail cooldown (600 s); non-retryable errors skip to the next candidate.
- `tools/test_fallback.py` self-check (6 scenarios) covering fallback, retry, cooldown, and all-fail behavior.

## [2.3.0] - 2026-07-03
### Added
- Scheduled reminder system using APScheduler + SQLite:
  - `services/reminder.py`: Background scheduler, SQLite `reminders` table, LINE Push API delivery.
  - Natural language parsing: supports `提醒我 X分鐘後 ...` and `remind me to ... in X分鐘後`.
  - `提醒列表` / `取消提醒 #[id]` for management.
  - Per-user pending cap (`MAX_PENDING_REMINDERS`, default 20) and auto-cleanup of sent/cancelled rows after 7 days.
  - First-request lazy startup of the scheduler alongside keepalive.

## [2.2.1] - 2026-07-03
### Fixed
- Deferred `keepalive` startup until the first request so Gunicorn/Render boot no longer starts the background thread during worker import, while still preserving the heartbeat after the app starts serving traffic.

### Notes
- This is a patch release on `main` and follows the even-MAJOR versioning policy documented in `SPEC.md`.

## [2.2.0] - 2026-07-03
### Added
- Added SQLite-backed chat history storage via `services/database.py` and `services/chat_history.py`.
- Added authenticated database read/download APIs:
  - `GET /api/db/download`
  - `GET /api/db/stats`
  - `GET /api/db/export`
  - `GET /api/db/messages`
  - `GET /api/db/users`
  - `GET /api/db/user/<user_id>/history`
  - `GET /api/db/maintenance`
- Added `DATABASE_PATH` and `API_SECRET_KEY` configuration.
- Added `.env.example` entries for all supported runtime configuration values.

### Changed
- AI text and image interactions now persist user/model messages to SQLite.
- AI prompt history now prefers SQLite and falls back to Google Sheets if SQLite history is unavailable.
- Preserved non-blocking Google Sheet writes and message-id-based image temp paths from `2.1.1`.
- `config.py` now supports environment-variable overrides for all used config fields, including integer parsing for `CHAT_HISTORY_LENGTH` and `KEEPALIVE_INTERVAL`.

### Security
- Database APIs require `API_SECRET_KEY`; if unset, database API requests return `503`.
- Upload-based database endpoints `POST /api/db/restore` and `POST /api/db/validate` are explicitly disabled and return `403`.

## [2.1.1] - 2026-07-02
### Fixed
- Made `save_message` async (non-blocking) using threading to prevent blocking webhook handler.
- Fixed GAS catch block `error` variable bug (L79, L106) - changed to use `err`.
- Fixed history role detection - now uses `userId === "bot"` to identify model responses; added bot reply saving in line_handler.
- Fixed image path concurrency issue - now uses `message_id` as filename and cleans up temp files.
- Updated README model references from `gemini-2.5-flash` to `gemini-flash-latest` (long-term alias).
### Added
- Complete deployment guide `DEPLOYMENT.md`.

## [2.1.0] - 2026-04-17
### Changed
- Switched Gemini model to long-term alias `gemini-flash-latest` for automatic version migration when upstream models are retired.

## [2.0.0] - 2025-12-25
### Changed
- Migrated to new `google-genai` SDK.
- Unified use of `gemini-flash-latest` model (long-term alias).
- Used `genai.Client()` instead of `genai.configure()`.
- Used `client.chats.create()` for multi-turn conversations.
### Removed
- Deprecated `google-generativeai` package.

## [1.0.0] - 2025-12-25
### Added
- Initial modular refactor.
