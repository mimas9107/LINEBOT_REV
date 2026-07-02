---
name:          "CHANGELOG.md"
description:   "Project change history"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/07/02 11:00:00"
project_version: "2.1.1"
document_version: "1.0.2"
agent_sign: ['gemini cli/current_agent']
---

# Changelog

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
