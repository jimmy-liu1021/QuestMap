"""Validate and atomically save the first complete quest response from a page visit."""
import argparse
from datetime import datetime, timezone
import json
from math import asin, cos, degrees, radians, sin
from pathlib import Path

from convert_data import number
from plan_area_scan import scan_plan
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


def read_area(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict) or not isinstance(config.get("areas"), list) or len(config["areas"]) != 1:
        raise ProbeError("expected_one_area")
    area = config["areas"][0]
    if not isinstance(area, dict):
        raise ProbeError("invalid_area")
    lat = number(area.get("latitude"), 90)
    lng = number(area.get("longitude"), 180)
    radius = number(area.get("radius_km"), 100)
    if lat is None or lng is None or radius is None or radius <= 0 or abs(lat) + degrees(radius / 6371) >= 90:
        raise ProbeError("invalid_area")
    return {"latitude": lat, "longitude": lng}, radius


def covers_circle(bounds, location, radius):
    lat, lng = location["latitude"], location["longitude"]
    angle = radius / 6371
    dy = degrees(angle)
    dx = degrees(asin(sin(angle) / cos(radians(lat))))
    north, east, south, west = bounds
    return south <= lat - dy and lat + dy <= north and west <= lng - dx and lng + dx <= east


def filter_area(body, location, radius):
    latitude = radians(location["latitude"])
    longitude = location["longitude"]
    limit = sin(radius / (2 * 6371)) ** 2
    records = []
    for row in normalize(body):
        lat = radians(float(row["c"]))
        lng = radians(float(row["d"]) - longitude)
        if sin((lat - latitude) / 2) ** 2 + cos(latitude) * cos(lat) * sin(lng / 2) ** 2 <= limit:
            records.append(row)
    return json.dumps({"fp": records}).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data/quests.json")
    parser.add_argument("--area-config", type=Path)
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--plan-output", type=Path, help="write a fixed-zoom plan from the measured rectangle")
    parser.add_argument("--scan", action="store_true", help="collect all required fixed-zoom viewports")
    args = parser.parse_args()
    if args.scan and (not args.area_config or args.probe_only):
        parser.error("--scan requires --area-config and writes only after complete coverage")
    if args.plan_output and not (args.area_config and args.probe_only):
        parser.error("--plan-output requires --area-config and --probe-only")
    if args.plan_output and args.plan_output.resolve() == args.output.resolve():
        parser.error("plan output must differ from the snapshot path")
    args.headed, args.zoom_once, args.wait_seconds = False, False, 30 if args.area_config else 15
    try:
        if args.area_config:
            args.location, radius = read_area(args.area_config)
            if args.scan:
                args.scan_radius = radius
    except (OSError, ValueError, ProbeError):
        print("Update failed: invalid_area_config")
        return 1
    candidates = []
    report = run(args, on_valid=candidates.append)
    if args.area_config:
        print("Playwright summary:", json.dumps(report, sort_keys=True))
    if report["outcome"] != "valid_quests" or not candidates:
        print("Update failed:", report["outcome"])
        return 1
    try:
        body = candidates[0]
        if args.area_config:
            covered = (report.get("scan_coverage_complete", False) if args.scan else
                       covers_circle(report["bounds"], args.location, radius))
            body = filter_area(body, args.location, radius)
            count = len(json.loads(body)["fp"])
            print(f"Bounds (north/east/south/west): {report['bounds']}")
            print(f"Radius: {radius:g} km; valid unique rows in radius: {count}; covered: {covered}")
            if args.plan_output:
                artifact = scan_plan(args.location, radius, report["bounds"])
                replace_snapshot(args.plan_output, artifact)
                print(f"Planned fixed-zoom windows: {artifact['planned_window_count']}")
            if not args.probe_only and not covered:
                raise ProbeError("area_coverage_incomplete")
        if args.probe_only:
            return 0
        outcome, count = update(args.output, body)
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
