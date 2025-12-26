# Amazon Photos Sync

A tool to backup and migrate your Amazon Photos library with full deduplication and verification.

## Features

- **Complete enumeration** of your Amazon Photos library
- **MD5-based deduplication** - only downloads unique files
- **Verification mode** - check for new files before migration
- **Resume support** - safely handles interruptions
- **SQLite manifest** - complete audit trail of all files

## Requirements

- Python 3.10+
- Playwright (for browser automation)
- Amazon Photos account

## Installation

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install playwright
playwright install chromium
```

## Setup

1. Run the session saver to authenticate:
```bash
python amazon_save_session.py
```

2. Log into Amazon Photos in the browser window (60 seconds)

3. Session is saved to `amazon_session` file

## Usage

### Build manifest of all files
```bash
python amazon_photos_sync.py enumerate
```

### Download all unique files
```bash
python amazon_photos_sync.py download
```

### Check for new files (before migration)
```bash
python amazon_photos_sync.py verify
```

### View current status
```bash
python amazon_photos_sync.py status
```

## Options

- `--full` - Full month-by-month scan for enumerate (more thorough)
- `--limit N` - Limit download to N files
- `--no-verify` - Skip MD5 verification on download

## Safety

- **Read-only by default** - no deletions
- All downloads verified via MD5 hash
- Complete manifest maintained in SQLite
- Session files excluded from git

## License

MIT
