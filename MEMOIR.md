---
name:          "MEMOIR.md"
description:   "Project architectural memory and decisions"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/09/23 10:00:00"
project_version: "2.6.0"
document_version: "1.4.0"
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
- **Per-tool Risk Policy (D3/D4)**: each tool may declare `policy.risk` (`READ_ONLY`/`WRITE`/`DESTRUCTIVE`, default `READ_ONLY`); the registry exports a `POLICY` map. `AITextService._is_authorized` is checked before execution: READ_ONLY is open to everyone; WRITE/DESTRUCTIVE require a personal (`user`) identity listed in `HACKMD_ALLOWED_USER_IDS`. Group/room identities are strictly read-only (D7) — even a whitelisted group_id cannot create/update/delete. `user_id`/`user_scope` flow from `line_handler` (derived from `event.source.type`) through `chat_with_ai()` → `chat()` → the tool loop.
- **Async Tool Handlers (D2)**: the tool loop runs inside a single `asyncio.run()` per request; handlers declared as coroutines are `await`ed via `inspect.iscoroutinefunction`. Today's HackMD handlers are synchronous; async support is reserved for future plugins. The `asyncio.run()` wrapper was chosen over restructuring the whole sync service.
- **SPEC Decoupling (D6)**: `SPEC.md` records only mechanisms and policy (whitelist loading, duplicate-name startup error, `REQUIRED_ENV`, tool-loop caps, risk-policy check, async support) — never the per-plugin tool inventory. Tool listings and permissions live in the plugin modules and `README.md`; future plugins (e.g. TRA) no longer touch SPEC.
- **HackMD Plugin**: inlined synchronous client (`services/hackmd_tools.py`) using the existing `requests` dependency (D1) — no new git dependency, no `httpx`. 60s module-level cache for the note list (invalidated by write operations), 8s HTTP timeout, content truncated at 2000 chars, `_sanitize_error` reuse for token safety. Verified against the actual HackMD API field names (`createdAt` camelCase, not `created_at`).
- **TRA Plugin (D1–D6, rev2.6.0)**: `services/plugins/tra.py` injects the sibling `trachecker` project via `sys.path` (`Path(__file__).resolve().parents[3] / "trachecker"`) and re-exports 5 of its 6 `agent_tools` tools (dropped the `resolve_tra_station` primitive — the other 5 handlers resolve station names internally and return candidate hints on failure, so Gemini can self-correct next round). All 5 are READ_ONLY. Handler adapter `lambda _n=_name, **_kw: dispatch(_n, _kw)` matches the tool-loop `handler(**args)` contract. Reuses the weather plugin's `TDX_CLIENT_ID`/`TDX_CLIENT_SECRET` (no new env vars). Relies on the sibling-repo directory layout; if absent, the loader import fails and the plugin is skipped without crashing (importer catches `Exception`). Fare is a TDX v2 estimate (official fare wins) and itinerary has no-direct-train limits (e.g. 六家→臺北 must be split) — both surfaced via tool descriptions/hints, not re-phrased in the plugin layer.
- **Deployment**: Complete deployment guide available in `DEPLOYMENT.md` covering Google Sheets/GAS setup, LINE Developer console, and Render.com.
