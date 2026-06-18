---
name:          "CHANGELOG.md"
description:   "Project change history"
created_date:  "2026/06/18 10:00:00"
modified_date: "2026/06/18 10:00:00"
project_version: "2.1.0"
document_version: "1.0.0"
agent_sign: ['gemini cli/current_agent']
---

# Changelog

## [2.1.0] - 2026-04-17
### Added
- Updated Gemini model to long-term alias `gemini-flash-latest` for stable service.
- Automatic transition when models are retired.

## [2.0.0] - 2025-12-25
### Changed
- Migrated to new `google-genai` SDK.
- Unified use of `gemini-2.5-flash` model.
- Used `genai.Client()` instead of `genai.configure()`.
- Used `client.chats.create()` for multi-turn conversations.
### Removed
- Deprecated `google-generativeai` package.

## [1.0.0] - 2025-12-25
### Added
- Initial modular refactor.
