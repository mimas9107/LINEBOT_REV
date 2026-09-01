---
name:          "CHANGELOG.md"
description:   "Project change history"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/09/01 13:30:00"
project_version: "2.3.4"
document_version: "1.4.0"
agent_sign: ['gemini cli/current_agent', 'codex/current_agent', 'opencode/current_agent']
---

# Changelog

## [2.3.4] - 2026-09-01
### Changed
- `MODEL_LIST` candidate order reordered: `gemini-2.5-flash` promoted to first candidate, `gemini-flash-latest` (markfail=True) demoted to third. Rationale: the first candidate is tried up to 3 times on 503 (worst backoff-latency path), so the currently-healthy model should lead; `markfail` remains the real self-healing mechanism. `tools/test_fallback.py` refactored to be order-agnostic (derives PRIMARY/BACKUP/markfail model dynamically from `MODEL_LIST`), 8/8 pass.
### Added
- Per-request message-id correlation for traceable logs: new `services/logctx.py` holds the current `msgid` in a `threading.local`; `LineHandler` sets it at the start of each event, and `[LineHandler]` / `[AITextService]` / `[AIImageService]` log lines now carry `msgid=<id>`. A single message's full lifecycle (receive → model retry chain → reply) is now extractable with `rg "msgid="`, removing the need to eyeball microsecond timestamps when diagnosing which reply answered which question.
### Notes
- Logging-only change; the reply path is unchanged (still synchronous `reply_message`, no `push_message`/free-tier 500/month quota risk). Patch release on `main`, following the even-MAJOR versioning policy.
- Render Start Command is now version-controlled: `Procfile` is the single source of truth (`web: gunicorn app:app --timeout 300 --worker 1`), documented in `DEPLOYMENT.md`. `--worker 1` is intentional (single-process keepalive/reminder design); Render dashboard's Start Command should mirror the `Procfile` exactly.

## [2.3.3] - 2026-09-01
### Added
- Versioned `Procfile` (`web: gunicorn app:app --timeout 300`) so the gunicorn timeout fix is no longer dashboard-only and survives redeploys / setting resets.
- Image analysis resilience: `AIImageService` now iterates the `MODEL_LIST` fallback chain with 503/429 exponential-backoff retry and `markfail` cooldown, reaching parity with the text path (`services/ai_image.py`).
- History prompt guard: `LineHandler._format_chat_history` truncates any single history message over `MAX_HISTORY_MSG_LEN` (1000 chars), preventing long AI replies from inflating the prompt linearly and pushing up timeout risk.
- `tools/test_fallback.py` extended with 2 image-path cases (fallback on 503, all-fail raises) — now 8 scenarios, 8/8 pass.

### Notes
- Single sync worker (default) trade-off now explicit: with `--timeout 300`, one stalled request can occupy the only worker for up to 5 minutes, during which `/health` and `/about` are also unresponsive. Not changed here — keepalive/reminder lazy-start are single-process designed; revisit if WORKER TIMEOUT persists or concurrency is needed.
- Patch release on `main`, following the even-MAJOR versioning policy.

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
