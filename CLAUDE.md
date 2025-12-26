# Claude Code Guidelines for Amazon Photos Sync

## CRITICAL SAFETY RULES

### NO DELETIONS WITHOUT EXPLICIT APPROVAL
- **NEVER** delete files from Amazon Photos without explicit user approval
- **NEVER** delete local files without explicit user approval
- **NEVER** implement bulk delete functionality without user confirmation
- All delete operations must be opt-in and require explicit confirmation

### Data Integrity
- All downloads MUST be verified via MD5 hash
- Never overwrite existing local files without verification
- Maintain complete manifest of all files before any operations
- Operations must be resumable - no partial state that could cause data loss

### Session Security
- NEVER commit session files, cookies, or credentials
- Session files (amazon_session, cookies.json) must remain in .gitignore
- Do not log or expose sensitive authentication tokens

## Project Goals

1. **Enumerate** - Build complete manifest of Amazon Photos library
2. **Download** - Download all unique files (deduplicated by MD5)
3. **Verify** - Check for new files before migration
4. **Migrate** - Upload to Google Photos with verification

## Architecture Principles

- Read-only by default - no modifications without explicit mode
- Idempotent operations - safe to re-run at any time
- Resume support - handle interruptions gracefully
- Complete audit trail via SQLite manifest

## File Organization

```
amazon_photos_backup/
  {md5_prefix}/
    {md5}.{ext}  # Files organized by MD5 to handle duplicates
```

## Commands

```bash
python amazon_photos_sync.py enumerate   # Build/update manifest
python amazon_photos_sync.py download    # Download unique files
python amazon_photos_sync.py verify      # Check for new files
python amazon_photos_sync.py status      # Show statistics
```
