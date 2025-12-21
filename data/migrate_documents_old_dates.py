#!/usr/bin/env python3
"""
Migration script that sets all document dates to 1 year ago.

Usage from host:
    docker compose exec bot python /app/data/migrate_documents_old_dates.py [--dry-run]
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta


def migrate_file(input_file: Path, output_file: Path, old_date: str, dry_run: bool = False):
    """Migrate a single JSON file with a backdated timestamp."""
    print(f"\n📄 Processing: {input_file.name}")

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total, converted = 0, 0

    def add_date(doc):
        nonlocal total, converted
        total += 1
        metadata = doc.get('metadata', {})

        if 'document_date' not in metadata:
            metadata['document_date'] = old_date
            print(f"  → {metadata.get('title', 'Unknown')}: {old_date}")
            doc['metadata'] = metadata
            converted += 1
        return doc

    if isinstance(data, list):
        data = [add_date(doc) for doc in data]
    elif isinstance(data, dict) and 'documents' in data:
        data['documents'] = [add_date(doc) for doc in data['documents']]
    elif isinstance(data, dict):
        data = add_date(data)

    if not dry_run:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Wrote to: {output_file}")
    else:
        print(f"  [DRY RUN] Would write to: {output_file}")

    return total, converted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--years-ago', type=int, default=1, help='Years to backdate (default: 1)')
    args = parser.parse_args()

    # Calculate date N years ago
    backdated = datetime.now() - timedelta(days=365 * args.years_ago)
    old_date = backdated.strftime('%Y-%m-%d')

    archive = Path('/app/data/manual_docs/archive')
    active = Path('/app/data/manual_docs/active')

    print("=" * 70)
    print("Document Date Migration (Backdated)")
    print("=" * 70)
    print(f"Setting all documents to: {old_date} ({args.years_ago} year(s) ago)")
    print("=" * 70)

    json_files = list(archive.glob('*.json'))
    total_files, total_docs, total_converted = 0, 0, 0

    for json_file in json_files:
        if json_file.name.lower() in ['readme.json', 'example_document.json']:
            continue

        docs, converted = migrate_file(json_file, active / json_file.name, old_date, args.dry_run)
        total_files += 1
        total_docs += docs
        total_converted += converted

    print("\n" + "=" * 70)
    print(f"Files: {total_files} | Documents: {total_docs} | Converted: {total_converted}")

    if not args.dry_run:
        print("\n✓ Done! Run: python run_ingestion.py --recreate")
    else:
        print("\n[DRY RUN] Run without --dry-run to apply changes")

    print("=" * 70)


if __name__ == "__main__":
    main()
