#!/usr/bin/env python3
"""
Amazon Photos Sync Tool

Modes:
  enumerate  - Scan Amazon Photos and build/update manifest
  download   - Download files (deduplicated by MD5)
  verify     - Check for new files in Amazon Photos not in manifest
  status     - Show current sync status

Usage:
  python amazon_photos_sync.py enumerate    # Build/update manifest
  python amazon_photos_sync.py download     # Download all unique files
  python amazon_photos_sync.py verify       # Check for new files
  python amazon_photos_sync.py status       # Show statistics
"""

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import async_playwright

# Configuration
SESSION_FILE = "amazon_session"
MANIFEST_DB = "amazon_photos_manifest.db"
DOWNLOAD_DIR = "amazon_photos_backup"
OWNER_ID = "A1J9A4AQRPPQRR"  # Your Amazon account owner ID


def init_db():
    """Initialize SQLite manifest database."""
    conn = sqlite3.connect(MANIFEST_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            name TEXT,
            md5 TEXT,
            size INTEGER,
            content_type TEXT,
            extension TEXT,
            created_date TEXT,
            modified_date TEXT,
            content_date TEXT,
            source TEXT,
            first_seen TEXT,
            last_seen TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            md5 TEXT PRIMARY KEY,
            local_path TEXT,
            downloaded_at TEXT,
            source_id TEXT,
            verified INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT,
            started_at TEXT,
            completed_at TEXT,
            files_found INTEGER,
            files_new INTEGER,
            status TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_md5 ON files(md5)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_files_last_seen ON files(last_seen)")
    conn.commit()
    return conn


def get_db():
    """Get database connection."""
    return sqlite3.connect(MANIFEST_DB)


async def enumerate_files(full_scan=False):
    """Enumerate all files in Amazon Photos and update manifest."""
    print("=" * 70)
    print("ENUMERATE: Scanning Amazon Photos")
    print("=" * 70)

    conn = init_db()
    run_id = conn.execute(
        "INSERT INTO sync_runs (run_type, started_at, status) VALUES (?, ?, ?)",
        ("enumerate", datetime.now().isoformat(), "running")
    ).lastrowid
    conn.commit()

    captured_items = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=SESSION_FILE)
        page = await context.new_page()

        async def capture_response(response):
            if '/drive/v1/search' in response.url or '/drive/v1/nodes' in response.url:
                try:
                    body = await response.json()
                    if 'data' in body:
                        captured_items.extend(body['data'])
                except:
                    pass

        page.on("response", capture_response)

        # Build list of URLs to visit - years and months for thorough coverage
        urls_to_visit = [
            ("All Photos", "https://www.amazon.com/photos/all"),
            ("Videos", "https://www.amazon.com/photos/videos"),
        ]

        # Add years from 2010 to current year
        current_year = datetime.now().year
        for year in range(current_year, 2009, -1):
            urls_to_visit.append((f"Year {year}", f"https://www.amazon.com/photos/all?timeYear={year}"))

        # If full scan, also do month-by-month for recent years
        if full_scan:
            for year in range(current_year, current_year - 3, -1):
                for month in range(1, 13):
                    urls_to_visit.append(
                        (f"{year}-{month:02d}",
                         f"https://www.amazon.com/photos/all?timeYear={year}&timeMonth={month}")
                    )

        total_urls = len(urls_to_visit)
        for idx, (label, url) in enumerate(urls_to_visit, 1):
            print(f"[{idx}/{total_urls}] Scanning {label}...", end=" ", flush=True)
            before_count = len(captured_items)

            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_timeout(3000)

                # Scroll to load more
                last_count = len(captured_items)
                no_change = 0
                for scroll in range(50):  # Up to 50 scrolls per page
                    await page.evaluate("window.scrollBy(0, 5000)")
                    await page.wait_for_timeout(600)

                    if len(captured_items) == last_count:
                        no_change += 1
                        if no_change >= 5:
                            break
                    else:
                        no_change = 0
                    last_count = len(captured_items)

                new_items = len(captured_items) - before_count
                print(f"+{new_items} (total: {len(captured_items)})")
            except Exception as e:
                print(f"Error: {e}")

        await browser.close()

    # Process and deduplicate captured items
    print(f"\nProcessing {len(captured_items)} captured items...")

    now = datetime.now().isoformat()
    files_found = 0
    files_new = 0
    seen_ids = set()

    for item in captured_items:
        file_id = item.get('id')
        if not file_id or file_id in seen_ids:
            continue
        seen_ids.add(file_id)

        props = item.get('contentProperties', {})

        # Check if exists
        existing = conn.execute("SELECT id FROM files WHERE id = ?", (file_id,)).fetchone()

        if existing:
            # Update last_seen
            conn.execute("UPDATE files SET last_seen = ? WHERE id = ?", (now, file_id))
        else:
            # Insert new file
            conn.execute("""
                INSERT INTO files (id, name, md5, size, content_type, extension,
                                   created_date, modified_date, content_date, source,
                                   first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id,
                item.get('name', 'unknown'),
                props.get('md5'),
                props.get('size', 0),
                props.get('contentType', 'unknown'),
                props.get('extension', ''),
                item.get('createdDate'),
                item.get('modifiedDate'),
                props.get('contentDate'),
                item.get('createdBy', 'unknown'),
                now,
                now
            ))
            files_new += 1

        files_found += 1

    conn.execute("""
        UPDATE sync_runs SET completed_at = ?, files_found = ?, files_new = ?, status = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), files_found, files_new, "completed", run_id))
    conn.commit()

    # Print summary
    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    unique_md5s = conn.execute("SELECT COUNT(DISTINCT md5) FROM files WHERE md5 IS NOT NULL").fetchone()[0]

    print(f"\n{'=' * 70}")
    print("ENUMERATION COMPLETE")
    print("=" * 70)
    print(f"Files found this scan: {files_found:,}")
    print(f"New files added: {files_new:,}")
    print(f"Total files in manifest: {total_files:,}")
    print(f"Unique MD5 hashes: {unique_md5s:,}")
    print(f"Duplicates: {total_files - unique_md5s:,}")

    conn.close()


async def download_files(limit=None, verify_md5=True):
    """Download all unique files (by MD5) that haven't been downloaded yet."""
    print("=" * 70)
    print("DOWNLOAD: Fetching files from Amazon Photos")
    print("=" * 70)

    conn = get_db()

    # Get unique MD5s that haven't been downloaded
    query = """
        SELECT DISTINCT f.md5, f.id, f.name, f.size, f.extension, f.content_type
        FROM files f
        LEFT JOIN downloads d ON f.md5 = d.md5
        WHERE f.md5 IS NOT NULL AND d.md5 IS NULL
        ORDER BY f.size DESC
    """
    pending = conn.execute(query).fetchall()

    if limit:
        pending = pending[:limit]

    total_to_download = len(pending)
    total_size = sum(row[3] for row in pending)

    print(f"Files to download: {total_to_download:,}")
    print(f"Total size: {format_size(total_size)}")
    print()

    if total_to_download == 0:
        print("Nothing to download!")
        conn.close()
        return

    # Create download directory
    download_path = Path(DOWNLOAD_DIR)
    download_path.mkdir(exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=SESSION_FILE)
        page = await context.new_page()

        # Navigate to photos to establish session
        await page.goto("https://www.amazon.com/photos/all", timeout=30000)
        await page.wait_for_timeout(2000)

        downloaded = 0
        failed = 0
        skipped = 0

        for idx, (md5, file_id, name, size, ext, content_type) in enumerate(pending, 1):
            # Determine local filename - use MD5 prefix for organization
            prefix = md5[:2]
            ext_clean = ext.lower() if ext else get_extension(content_type)
            local_dir = download_path / prefix
            local_dir.mkdir(exist_ok=True)
            local_file = local_dir / f"{md5}.{ext_clean}"

            # Skip if already exists and correct size
            if local_file.exists() and local_file.stat().st_size == size:
                conn.execute("""
                    INSERT OR REPLACE INTO downloads (md5, local_path, downloaded_at, source_id, verified)
                    VALUES (?, ?, ?, ?, ?)
                """, (md5, str(local_file), datetime.now().isoformat(), file_id, 1))
                conn.commit()
                skipped += 1
                print(f"[{idx}/{total_to_download}] Skipped (exists): {name[:50]}")
                continue

            print(f"[{idx}/{total_to_download}] Downloading: {name[:50]} ({format_size(size)})", end="", flush=True)

            try:
                # Build download URL
                download_url = f"https://www.amazon.com/drive/v1/nodes/{file_id}/contentRedirection?querySuffix=%3Fdownload%3Dtrue"

                # Use page.evaluate to fetch with credentials
                # First get the redirect URL
                result = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const response = await fetch("{download_url}", {{
                                credentials: 'include',
                                redirect: 'follow'
                            }});
                            const blob = await response.blob();
                            const arrayBuffer = await blob.arrayBuffer();
                            const uint8Array = new Uint8Array(arrayBuffer);
                            return {{
                                success: true,
                                data: Array.from(uint8Array),
                                size: blob.size,
                                type: blob.type
                            }};
                        }} catch (e) {{
                            return {{success: false, error: e.toString()}};
                        }}
                    }}
                """)

                if result.get('success'):
                    # Write file
                    file_data = bytes(result['data'])
                    local_file.write_bytes(file_data)

                    # Verify MD5 if requested
                    if verify_md5:
                        actual_md5 = hashlib.md5(file_data).hexdigest()
                        if actual_md5 != md5:
                            print(f" - MD5 MISMATCH! Expected {md5}, got {actual_md5}")
                            failed += 1
                            local_file.unlink()
                            continue

                    # Record download
                    conn.execute("""
                        INSERT OR REPLACE INTO downloads (md5, local_path, downloaded_at, source_id, verified)
                        VALUES (?, ?, ?, ?, ?)
                    """, (md5, str(local_file), datetime.now().isoformat(), file_id, 1 if verify_md5 else 0))
                    conn.commit()

                    downloaded += 1
                    print(" - OK")
                else:
                    print(f" - FAILED: {result.get('error', 'Unknown error')}")
                    failed += 1

                # Small delay to be nice to Amazon
                await page.wait_for_timeout(200)

            except Exception as e:
                print(f" - ERROR: {e}")
                failed += 1

        await browser.close()

    print(f"\n{'=' * 70}")
    print("DOWNLOAD COMPLETE")
    print("=" * 70)
    print(f"Downloaded: {downloaded:,}")
    print(f"Skipped (already exists): {skipped:,}")
    print(f"Failed: {failed:,}")

    conn.close()


async def verify_sync():
    """Check for new files in Amazon Photos that aren't in manifest."""
    print("=" * 70)
    print("VERIFY: Checking for new files in Amazon Photos")
    print("=" * 70)

    conn = get_db()

    # Get current manifest state
    manifest_ids = set(row[0] for row in conn.execute("SELECT id FROM files").fetchall())
    manifest_md5s = set(row[0] for row in conn.execute("SELECT DISTINCT md5 FROM files WHERE md5 IS NOT NULL").fetchall())

    print(f"Manifest contains: {len(manifest_ids):,} files, {len(manifest_md5s):,} unique MD5s")
    print("\nScanning Amazon Photos for new files...")

    captured_items = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=SESSION_FILE)
        page = await context.new_page()

        async def capture_response(response):
            if '/drive/v1/search' in response.url or '/drive/v1/nodes' in response.url:
                try:
                    body = await response.json()
                    if 'data' in body:
                        captured_items.extend(body['data'])
                except:
                    pass

        page.on("response", capture_response)

        # Quick scan of recent content
        urls = [
            ("All Photos", "https://www.amazon.com/photos/all"),
            ("Recent", f"https://www.amazon.com/photos/all?timeYear={datetime.now().year}"),
        ]

        for label, url in urls:
            print(f"  Scanning {label}...", end=" ", flush=True)
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(3000)

            for _ in range(30):
                await page.evaluate("window.scrollBy(0, 5000)")
                await page.wait_for_timeout(500)

            print(f"captured {len(captured_items)} items")

        await browser.close()

    # Check for new files
    new_files = []
    new_md5s = set()
    seen_ids = set()

    for item in captured_items:
        file_id = item.get('id')
        if not file_id or file_id in seen_ids:
            continue
        seen_ids.add(file_id)

        if file_id not in manifest_ids:
            props = item.get('contentProperties', {})
            md5 = props.get('md5')
            new_files.append({
                'id': file_id,
                'name': item.get('name'),
                'md5': md5,
                'size': props.get('size', 0),
                'content_type': props.get('contentType'),
                'created': item.get('createdDate')
            })
            if md5:
                new_md5s.add(md5)

    print(f"\n{'=' * 70}")
    print("VERIFICATION RESULTS")
    print("=" * 70)

    if new_files:
        # Check if any new files are actually new content (not just duplicates)
        truly_new = [f for f in new_files if f['md5'] not in manifest_md5s]
        duplicates_of_existing = [f for f in new_files if f['md5'] in manifest_md5s]

        print(f"\nNew files found: {len(new_files)}")
        print(f"  - Truly new content: {len(truly_new)}")
        print(f"  - Duplicates of existing: {len(duplicates_of_existing)}")

        if truly_new:
            print("\nTruly new files (first 20):")
            for f in truly_new[:20]:
                print(f"  - {f['name']} ({format_size(f['size'])}) - {f['created']}")

            if len(truly_new) > 20:
                print(f"  ... and {len(truly_new) - 20} more")

        print("\n*** Run 'enumerate' to add these to the manifest ***")
    else:
        print("\nNo new files found - manifest is up to date!")

    conn.close()


def show_status():
    """Show current sync status."""
    print("=" * 70)
    print("SYNC STATUS")
    print("=" * 70)

    if not Path(MANIFEST_DB).exists():
        print("\nNo manifest found. Run 'enumerate' first.")
        return

    conn = get_db()

    # File counts
    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    unique_md5s = conn.execute("SELECT COUNT(DISTINCT md5) FROM files WHERE md5 IS NOT NULL").fetchone()[0]
    total_size = conn.execute("SELECT SUM(size) FROM files").fetchone()[0] or 0

    # Download counts
    downloaded = conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0]
    downloaded_size = conn.execute("""
        SELECT SUM(f.size) FROM downloads d
        JOIN files f ON d.source_id = f.id
    """).fetchone()[0] or 0

    # Pending
    pending = unique_md5s - downloaded
    pending_size = conn.execute("""
        SELECT SUM(size) FROM (
            SELECT DISTINCT f.md5, f.size FROM files f
            LEFT JOIN downloads d ON f.md5 = d.md5
            WHERE f.md5 IS NOT NULL AND d.md5 IS NULL
        )
    """).fetchone()[0] or 0

    # Last sync
    last_enum = conn.execute("""
        SELECT completed_at, files_found, files_new FROM sync_runs
        WHERE run_type = 'enumerate' AND status = 'completed'
        ORDER BY completed_at DESC LIMIT 1
    """).fetchone()

    print(f"\nManifest Statistics:")
    print(f"  Total files tracked: {total_files:,}")
    print(f"  Unique content (MD5): {unique_md5s:,}")
    print(f"  Duplicate files: {total_files - unique_md5s:,}")
    print(f"  Total size: {format_size(total_size)}")

    print(f"\nDownload Progress:")
    print(f"  Downloaded: {downloaded:,} / {unique_md5s:,} ({downloaded/unique_md5s*100:.1f}%)" if unique_md5s > 0 else "  Downloaded: 0")
    print(f"  Downloaded size: {format_size(downloaded_size)}")
    print(f"  Pending: {pending:,} files ({format_size(pending_size)})")

    if last_enum:
        print(f"\nLast Enumeration:")
        print(f"  Date: {last_enum[0]}")
        print(f"  Files found: {last_enum[1]:,}")
        print(f"  New files: {last_enum[2]:,}")

    # Check download directory
    download_path = Path(DOWNLOAD_DIR)
    if download_path.exists():
        file_count = sum(1 for _ in download_path.rglob("*") if _.is_file())
        disk_size = sum(f.stat().st_size for f in download_path.rglob("*") if f.is_file())
        print(f"\nLocal Storage ({DOWNLOAD_DIR}/):")
        print(f"  Files on disk: {file_count:,}")
        print(f"  Disk usage: {format_size(disk_size)}")

    conn.close()


def format_size(bytes_val):
    """Format bytes as human-readable size."""
    if bytes_val is None:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


def get_extension(content_type):
    """Get file extension from content type."""
    mapping = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/heic': 'heic',
        'image/webp': 'webp',
        'video/mp4': 'mp4',
        'video/quicktime': 'mov',
        'video/x-msvideo': 'avi',
    }
    return mapping.get(content_type, 'bin')


async def main():
    parser = argparse.ArgumentParser(description="Amazon Photos Sync Tool")
    parser.add_argument('command', choices=['enumerate', 'download', 'verify', 'status'],
                        help="Command to run")
    parser.add_argument('--full', action='store_true',
                        help="Full scan (month-by-month for enumerate)")
    parser.add_argument('--limit', type=int,
                        help="Limit number of files to download")
    parser.add_argument('--no-verify', action='store_true',
                        help="Skip MD5 verification on download")

    args = parser.parse_args()

    if args.command == 'enumerate':
        await enumerate_files(full_scan=args.full)
    elif args.command == 'download':
        await download_files(limit=args.limit, verify_md5=not args.no_verify)
    elif args.command == 'verify':
        await verify_sync()
    elif args.command == 'status':
        show_status()


if __name__ == "__main__":
    asyncio.run(main())
