"""
Storage utilities for training data and snapshots.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path


# Directory setup
DATA_DIR = Path("data")
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
TRAINING_FILE = DATA_DIR / "training.jsonl"

# Ensure directories exist
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def save_snapshot(request_id: str, page_html: str, candidates: List[Dict[str, Any]],
                 accepted_index: int, metadata: Dict[str, Any]) -> str:
    """
    Save a healing request snapshot for debugging and training.

    Args:
        request_id: Unique request identifier
        page_html: Original page HTML
        candidates: List of candidate locators
        accepted_index: Index of accepted candidate (-1 if none)
        metadata: Additional metadata

    Returns:
        Path to saved snapshot file
    """
    timestamp = datetime.now().isoformat()

    snapshot = {
        "request_id": request_id,
        "timestamp": timestamp,
        "page_html": page_html,
        "candidates": candidates,
        "accepted_index": accepted_index,
        "metadata": metadata
    }

    filename = f"{request_id}.json"
    filepath = SNAPSHOTS_DIR / filename

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        return str(filepath)
    except Exception as e:
        print(f"Error saving snapshot: {e}")
        return None


def load_snapshot(request_id: str) -> Dict[str, Any]:
    """
    Load a snapshot by request ID.

    Args:
        request_id: Request identifier

    Returns:
        Snapshot dictionary or None if not found
    """
    filepath = SNAPSHOTS_DIR / f"{request_id}.json"

    if not filepath.exists():
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading snapshot: {e}")
        return None


def append_training_record(record: Dict[str, Any]) -> bool:
    """
    Append a training record to the training dataset.

    Args:
        record: Training record dictionary

    Returns:
        True if successful, False otherwise
    """
    # Add timestamp if not present
    if 'timestamp' not in record:
        record['timestamp'] = datetime.now().isoformat()

    try:
        with open(TRAINING_FILE, 'a', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False)
            f.write('\n')
        return True
    except Exception as e:
        print(f"Error appending training record: {e}")
        return False


def load_training_data(limit: int = None) -> List[Dict[str, Any]]:
    """
    Load training data from the training file.

    Args:
        limit: Maximum number of records to load (None for all)

    Returns:
        List of training records
    """
    records = []

    if not TRAINING_FILE.exists():
        return records

    try:
        with open(TRAINING_FILE, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        print(f"Skipping invalid JSON line: {line[:100]}...")
    except Exception as e:
        print(f"Error loading training data: {e}")

    return records


def get_training_stats() -> Dict[str, Any]:
    """
    Get statistics about the training data.

    Returns:
        Statistics dictionary
    """
    records = load_training_data()

    if not records:
        return {"total_records": 0}

    total_records = len(records)
    accepted_count = sum(1 for r in records if r.get('accepted_index', -1) >= 0)
    rejected_count = total_records - accepted_count

    # Calculate acceptance rate
    acceptance_rate = accepted_count / total_records if total_records > 0 else 0

    # Get date range
    timestamps = [r.get('timestamp') for r in records if r.get('timestamp')]
    if timestamps:
        timestamps.sort()
        date_range = {
            "earliest": timestamps[0],
            "latest": timestamps[-1]
        }
    else:
        date_range = None

    return {
        "total_records": total_records,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "acceptance_rate": acceptance_rate,
        "date_range": date_range
    }


def cleanup_old_snapshots(days_old: int = 30) -> int:
    """
    Clean up old snapshot files.

    Args:
        days_old: Remove snapshots older than this many days

    Returns:
        Number of files removed
    """
    from datetime import datetime, timedelta

    cutoff_date = datetime.now() - timedelta(days=days_old)
    removed_count = 0

    if not SNAPSHOTS_DIR.exists():
        return 0

    for filepath in SNAPSHOTS_DIR.glob("*.json"):
        try:
            # Check file modification time
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
            if mtime < cutoff_date:
                filepath.unlink()
                removed_count += 1
        except Exception:
            continue

    return removed_count


def export_training_data(output_file: str, format: str = "jsonl") -> bool:
    """
    Export training data to a different format.

    Args:
        output_file: Output file path
        format: Export format ("jsonl", "json", "csv")

    Returns:
        True if successful
    """
    records = load_training_data()

    try:
        if format == "jsonl":
            # Already in JSONL format, just copy
            with open(output_file, 'w', encoding='utf-8') as f:
                for record in records:
                    json.dump(record, f, ensure_ascii=False)
                    f.write('\n')

        elif format == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)

        elif format == "csv":
            # Simple CSV export (limited fields)
            import csv
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow(["request_id", "timestamp", "accepted_index", "candidate_count"])

                for record in records:
                    writer.writerow([
                        record.get("request_id", ""),
                        record.get("timestamp", ""),
                        record.get("accepted_index", -1),
                        len(record.get("candidates", []))
                    ])
        else:
            print(f"Unsupported format: {format}")
            return False

        return True

    except Exception as e:
        print(f"Error exporting training data: {e}")
        return False
