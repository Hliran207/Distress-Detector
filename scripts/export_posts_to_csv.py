"""
Export all documents from the MongoDB `posts` collection to a CSV file.

Usage (from project root, with .env containing MONGO_URI)::

    python scripts/export_posts_to_csv.py
    python scripts/export_posts_to_csv.py -o data/posts_backup.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

# Allow running as `python scripts/export_posts_to_csv.py` without PYTHONPATH
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.mongo_config import COLLECTION_NAME, DB_NAME, load_mongo_uri


def _cell_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def export_posts_to_csv(output_path: Path) -> int:
    uri = load_mongo_uri()
    client = MongoClient(uri)
    try:
        coll = client[DB_NAME][COLLECTION_NAME]
        docs = list(coll.find({}))
    finally:
        client.close()

    if not docs:
        print(f"No documents in {DB_NAME}.{COLLECTION_NAME}", file=sys.stderr)
        return 1

    rows: list[dict[str, str]] = []
    fieldnames: set[str] = set()
    for doc in docs:
        row: dict[str, str] = {}
        for key, raw in doc.items():
            row[key] = _cell_value(raw)
            fieldnames.add(key)
        rows.append(row)

    ordered = sorted(fieldnames)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in ordered})

    print(f"Wrote {len(rows):,} rows to {output_path.resolve()}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Export MongoDB posts collection to CSV.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("posts_export.csv"),
        help="Output CSV path (default: ./posts_export.csv)",
    )
    args = parser.parse_args()
    raise SystemExit(export_posts_to_csv(args.output))


if __name__ == "__main__":
    main()
