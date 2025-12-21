#!/usr/bin/env python3
"""
Migration script to add document_date field to existing documents.

This script:
1. Reads JSON files from archive folder
2. Converts 'last_updated' to 'document_date' if present
3. Writes updated documents to active folder
4. Preserves original files in archive

Usage:
    python scripts/migrate_document_dates.py [--dry-run]
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


def convert_last_updated_to_document_date(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert last_updated field to document_date.

    Args:
        doc: Document dictionary

    Returns:
        Updated document dictionary
    """
    metadata = doc.get('metadata', {})

    # If document_date already exists, don't overwrite
    if 'document_date' in metadata:
        print(f"  ✓ Document already has document_date: {metadata.get('title', 'Unknown')}")
        return doc

    # Try to convert last_updated to document_date
    if 'last_updated' in metadata:
        last_updated = metadata['last_updated']

        # Parse the date (assumes YYYY-MM-DD format)
        try:
            # Validate the date format
            datetime.strptime(last_updated, '%Y-%m-%d')
            metadata['document_date'] = last_updated
            print(f"  ✓ Converted last_updated → document_date: {metadata.get('title', 'Unknown')} ({last_updated})")
        except ValueError:
            print(f"  ⚠ Invalid date format in last_updated: {last_updated}, skipping conversion")
            # Use a default old date if conversion fails
            metadata['document_date'] = "2023-01-01"
            print(f"  → Using default date: 2023-01-01")
    else:
        # No last_updated field, use a default date (1 year ago)
        one_year_ago = datetime.now().replace(year=datetime.now().year - 1)
        metadata['document_date'] = one_year_ago.strftime('%Y-%m-%d')
        print(f"  → No last_updated field, using default: {metadata['document_date']}")

    doc['metadata'] = metadata
    return doc


def process_json_file(
    input_file: Path,
    output_file: Path,
    dry_run: bool = False
) -> tuple[int, int]:
    """
    Process a single JSON file.

    Args:
        input_file: Source file path
        output_file: Destination file path
        dry_run: If True, don't write files

    Returns:
        Tuple of (total_docs, converted_docs)
    """
    print(f"\n📄 Processing: {input_file.name}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total_docs = 0
        converted_docs = 0

        # Process based on structure
        if isinstance(data, list):
            # Array of documents
            updated_data = []
            for doc in data:
                total_docs += 1
                original_has_date = 'document_date' in doc.get('metadata', {})
                updated_doc = convert_last_updated_to_document_date(doc)
                updated_data.append(updated_doc)

                if not original_has_date and 'document_date' in updated_doc.get('metadata', {}):
                    converted_docs += 1

            result_data = updated_data

        elif isinstance(data, dict) and 'documents' in data:
            # Structured format: {"documents": [...]}
            updated_docs = []
            for doc in data['documents']:
                total_docs += 1
                original_has_date = 'document_date' in doc.get('metadata', {})
                updated_doc = convert_last_updated_to_document_date(doc)
                updated_docs.append(updated_doc)

                if not original_has_date and 'document_date' in updated_doc.get('metadata', {}):
                    converted_docs += 1

            data['documents'] = updated_docs
            result_data = data

        elif isinstance(data, dict):
            # Single document
            total_docs = 1
            original_has_date = 'document_date' in data.get('metadata', {})
            result_data = convert_last_updated_to_document_date(data)

            if not original_has_date and 'document_date' in result_data.get('metadata', {}):
                converted_docs = 1
        else:
            print(f"  ✗ Unknown JSON structure in {input_file}")
            return 0, 0

        # Write the updated file
        if not dry_run:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            print(f"  ✓ Wrote updated file to: {output_file}")
        else:
            print(f"  [DRY RUN] Would write to: {output_file}")

        return total_docs, converted_docs

    except Exception as e:
        print(f"  ✗ Error processing {input_file}: {e}")
        return 0, 0


def main():
    """Main migration process."""
    parser = argparse.ArgumentParser(
        description="Migrate documents to include document_date field",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without writing files'
    )
    parser.add_argument(
        '--archive-path',
        type=str,
        default='data/manual_docs/archive',
        help='Path to archive folder (default: data/manual_docs/archive)'
    )
    parser.add_argument(
        '--active-path',
        type=str,
        default='data/manual_docs/active',
        help='Path to active folder (default: data/manual_docs/active)'
    )

    args = parser.parse_args()

    # Get base directory (project root)
    base_dir = Path(__file__).parent.parent
    archive_dir = base_dir / args.archive_path
    active_dir = base_dir / args.active_path

    print("=" * 70)
    print("Document Date Migration Script")
    print("=" * 70)
    print(f"Archive folder: {archive_dir}")
    print(f"Active folder:  {active_dir}")
    print(f"Dry run:        {args.dry_run}")
    print("=" * 70)

    if not archive_dir.exists():
        print(f"\n✗ Error: Archive folder does not exist: {archive_dir}")
        return 1

    # Find all JSON files in archive
    json_files = list(archive_dir.glob('*.json'))

    if not json_files:
        print(f"\n✗ No JSON files found in {archive_dir}")
        return 1

    print(f"\nFound {len(json_files)} JSON file(s) to process")

    total_files = 0
    total_docs_processed = 0
    total_docs_converted = 0

    for json_file in json_files:
        # Skip README or example files
        if json_file.name.lower() in ['readme.json', 'example_document.json']:
            print(f"\n⏭  Skipping: {json_file.name}")
            continue

        # Determine output path
        output_file = active_dir / json_file.name

        # Process the file
        docs_processed, docs_converted = process_json_file(
            json_file,
            output_file,
            dry_run=args.dry_run
        )

        if docs_processed > 0:
            total_files += 1
            total_docs_processed += docs_processed
            total_docs_converted += docs_converted

    # Print summary
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"Files processed:       {total_files}")
    print(f"Documents processed:   {total_docs_processed}")
    print(f"Documents converted:   {total_docs_converted}")

    if args.dry_run:
        print("\n[DRY RUN] No files were modified")
        print("Run without --dry-run to apply changes")
    else:
        print("\n✓ Migration completed successfully!")
        print(f"\nNext steps:")
        print(f"1. Review the migrated files in: {active_dir}")
        print(f"2. Run ingestion with --recreate flag:")
        print(f"   python run_ingestion.py --recreate")

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
