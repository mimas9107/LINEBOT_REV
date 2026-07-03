opencode -s ses_0dd8e783affeP3ZNZY8GKTyfsV

# Merge Evaluation: feature2 into main

## Current State
- **main branch**: Latest version is v2.1.1, contains only minor fixes, no database storage for conversation history.
- **feature2 branch**: Implements database storage (SQLite) with backup/restore functionality, version v3.1.

## Changes in feature2 (since common commit 6502083)
- Added SQLite database service (`services/database.py`) with:
  - Maintenance mode to prevent writes during restore
  - Backup and atomic restore via `shutil.move`
  - WAL checkpoint and VACUUM after restore
  - Rollback mechanism on failure
- Added chat history service (`services/chat_history.py`) using SQLite
- Updated bookmark service to use async writing to Google Sheets
- Modified LINE handler to:
  - Check maintenance mode and discard messages during maintenance
  - Use async saving to Google Sheets to avoid blocking
  - Store both user and AI messages in SQLite
- Added REST API endpoints for database management:
  - `/api/db/download` - Download SQLite file
  - `/api/db/stats` - Database statistics
  - `/api/db/export` - Export as JSON
  - `/api/db/messages` - Query messages
  - `/api/db/users` - User statistics
  - `/api/db/user/<user_id>/history` - User history
  - `/api/db/maintenance` - Maintenance mode status
  - `/api/db/restore` - Restore database from uploaded file
  - `/api/db/validate` - Validate uploaded SQLite file
- Updated `app.py` to include new API routes and maintenance status in health check
- Updated documentation (README.md, SPEC.md, etc.) to reflect new features

## Analysis
### Benefits of Merging
1. **Persistence**: Conversation history is now stored in SQLite, preventing loss on platform restarts (e.g., Render's free tier).
2. **Backup and Restore**: Provides a mechanism to backup/restore functionality with maintenance mode and rollback for safety.
3. **API Access**: Enables programmatic access to chat data for analytics, export, etc.
4. **Minimal Impact on Existing Features**: Google Sheets bookmarking remains available via async writes.

### Risks and Considerations
1. **Complexity Increase**: The codebase grows significantly with new services and API endpoints.
2. **Testing Required**: The restore process involves file operations and thread locks; must be validated in a staging environment.
3. **Maintenance Overhead**: Administrators must now manage database backups and restores.
4. **Version Drift**: Merging will jump from v2.1.1 to v3.1, skipping intermediate versions (but this is acceptable as v2.1.1 only had minor fixes).

### Recommendation
The feature2 branch introduces a valuable and well-implemented feature set that addresses a critical limitation (ephemeral storage). The changes are modular and mostly additive, with clear separation of concerns.

**Verdict**: Suitable for merging into main after:
1. Deploying feature2 to a staging environment.
2. Testing the backup/restore flow, maintenance mode, and API endpoints.
3. Verifying that existing functionality (LINE webhook, Google Sheets bookmarking) remains intact.
4. Bumping the version to v3.1.1 (or following team versioning strategy) upon merge.

If immediate persistence is not required, the merge can be deferred, but the feature branch is stable and ready for production use.

---

## Additional Analysis: Restore Downtime Concern (2026-07-02)

### Issue
The `database.py` restore operation intentionally triggers **maintenance mode** (stops accepting new LINE messages) for ~2 seconds while replacing the SQLite file atomically. This causes a brief service interruption during manual restore.

### Root Cause
- SQLite file replacement requires atomic `os.replace`/`shutil.move` on POSIX
- Cannot safely swap DB file while connections may be reading/writing
- Maintenance mode ensures consistency — no partial reads, no lost writes

### Options Assessment

| Option | Pros | Cons |
|--------|------|------|
| **Keep feature2 as-is** | Works correctly; restore is rare (only after platform restart) | ~2s downtime per restore; adds custom maintenance logic |
| **Switch to managed PostgreSQL** (Render, Supabase, Neon free tier) | Native backup/restore; zero downtime; scales; standard tooling | Requires external DB setup; minor config changes |
| **Drop persistence entirely** (rely on Google Sheets) | Simplest; no new code | Loses local history; Sheets quota/latency issues |
| **Zero-downtime SQLite restore** (WAL + checkpoint + copy) | No maintenance mode | Complex; race-prone; over-engineered for this scale |

### Ponytail Recommendation
**If persistence across Render restarts is required** → **Option 2 (managed Postgres)**. Less custom code, standard operations, no maintenance-mode hacks.

**If persistence is optional** → **Option 3 (delete feature2)**. Simplest, avoids all complexity.

**Do not** pursue Option 4 — it adds significant complexity for marginal gain on a single-node free-tier bot.

### Decision Required
Confirm actual persistence requirement:
- **Yes, need survive restarts** → Migrate to Postgres, retire feature2 SQLite code.
- **No, Google Sheets is fine** → Abandon feature2 branch, keep main as-is.

*Additional analysis added on: 2026-07-02*
