---
name:          "CHANGELOG.md"
description:   "Project change history"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/07/02 10:00:00"
project_version: "2.1.0"
document_version: "1.0.1"
agent_sign: ['gemini cli/current_agent']
---

# Changelog

## [2.1.0] - 2026-07-02
### Fixed
- Task #1: Made `save_message` async (non-blocking) using threading to prevent blocking webhook handler.
- Task #2: Fixed GAS catch block `error` variable bug (L79, L106) - changed to use `err`.
- Task #3: Fixed history role detection - now uses `userId === "bot"` to identify model responses; added bot reply saving in line_handler.
- Task #4: Fixed image path concurrency issue - now uses `message_id` as filename and cleans up temp files.
- Task #5: Updated README model references from `gemini-2.5-flash` to `gemini-flash-latest` (long-term alias).

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
