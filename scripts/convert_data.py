"""Merge authorized JSON/gzip exports into a portable fp document."""
import argparse
import gzip
import json
import math
import os
from pathlib import Path
import tempfile


def number(value, limit):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        value = float(value)
    except (ValueError, OverflowError):
        return None
    return value if math.isfinite(value) and abs(value) <= limit else None


def read(path):
    content = path.read_bytes()
    if content.startswith(b"\x1f\x8b"):
        content = gzip.decompress(content)
    document = json.loads(content.decode("utf-8-sig"))
    if not isinstance(document, dict) or not isinstance(document.get("fp"), list):
        raise ValueError(f"{path}: expected an fp array")
    return document["fp"]


def merge(paths):
    records = {}
    invalid = duplicates = 0
    for path in paths:
        for item in read(path):
            lat = number(item.get("c"), 90) if isinstance(item, dict) else None
            lng = number(item.get("d"), 180) if isinstance(item, dict) else None
            if lat is None or lng is None:
                invalid += 1
                continue
            identifier = item.get("a")
            name = item.get("b")
            timestamp = number(item.get("g"), 8640000000000)
            if timestamp is None or timestamp < 0 or not timestamp.is_integer():
                timestamp = -1
            identifier = identifier.strip() if isinstance(identifier, str) else ""
            key = identifier or (lat, lng, name.strip() if isinstance(name, str) else "")
            if key in records:
                duplicates += 1
            if key not in records or timestamp >= records[key][0]:
                records[key] = (timestamp, item)
    return {"fp": [item for _, item in records.values()]}, invalid, duplicates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.resolve() in (path.resolve() for path in args.inputs):
            raise ValueError("output must differ from all inputs")
        data, invalid, duplicates = merge(args.inputs)
        if not data["fp"]:
            raise ValueError("no valid records to write")
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=args.output.parent, delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            try:
                temporary.write(encoded + "\n")
                temporary.close()
                os.replace(temp_path, args.output)
            finally:
                temp_path.unlink(missing_ok=True)
    except (OSError, ValueError, EOFError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{len(data['fp'])} records, {duplicates} duplicates, {invalid} invalid rows")


if __name__ == "__main__":
    main()

