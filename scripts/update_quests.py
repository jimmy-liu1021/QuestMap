"""Validate and atomically save the first complete quest response from a page visit."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from convert_data import number
from probe_api import ProbeError, replace_snapshot, validate
from probe_playwright import run


def normalize(body):
    rows = validate(body)["fp"]
    unique = {}
    for row in rows:
        name = row.get("b")
        if not isinstance(name, str) or not name.strip():
            raise ProbeError("invalid_station_name")
        identifier = (row.get("a") or "").strip()
        key = identifier or (float(row["c"]), float(row["d"]), name.strip())
        timestamp = number(row.get("g"), 8640000000000)
        rank = timestamp if timestamp is not None and timestamp >= 0 and timestamp.is_integer() else -1
        if key not in unique or rank >= unique[key][0]:
            unique[key] = (rank, row)
    return [unique[key][1] for key in sorted(unique, key=lambda key: (isinstance(key, tuple), key))]


def update(path, body):
    records = normalize(body)
    try:
        previous = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, ValueError):
        previous = None
    if isinstance(previous, dict) and previous.get("fp") == records and previous.get("updated_at"):
        return "unchanged", len(records)
    updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    replace_snapshot(path, {"updated_at": updated, "fp": records})
    return "updated", len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data/quests.json")
    args = parser.parse_args()
    args.headed, args.zoom_once, args.wait_seconds = False, False, 15
    candidates = []
    report = run(args, on_valid=candidates.append)
    if report["outcome"] != "valid_quests" or not candidates:
        print("Update failed:", report["outcome"])
        return 1
    try:
        outcome, count = update(args.output, candidates[0])
    except ProbeError as error:
        print("Update failed:", error)
        return 1
    except (OSError, ValueError):
        print("Update failed: output_error")
        return 1
    print(f"{outcome}: {count} unique records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
