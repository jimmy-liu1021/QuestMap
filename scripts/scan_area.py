"""Collect tasks through serial, ordinary drags of the visible map."""
import json
from math import asinh, hypot, radians, tan
from time import monotonic

from plan_area_scan import circle_coverage, plan
from probe_api import validate

MIN_INTERVAL_SECONDS = 8
MAX_QUEST_REQUESTS = 48


def mercator(latitude):
    return asinh(tan(radians(latitude)))


def drag_delta(bounds, target, pixel_width, pixel_height):
    north, east, south, west = bounds
    x = ((west + east) / 2 - target["longitude"]) / (east - west) * pixel_width
    top, bottom = mercator(north), mercator(south)
    y = (mercator(target["latitude"]) - (top + bottom) / 2) / (top - bottom) * pixel_height
    # A drag starts near the center and must end inside the map. Long moves
    # are split into intermediate views, which also contribute to coverage.
    scale = max(1, abs(x) / (pixel_width * 0.94), abs(y) / (pixel_height * 0.76))
    return x / scale, y / scale


def sweep(page, options, report, initial_body, initial_bounds, request_times, next_response, restricted):
    location, radius = options.location, options.scan_radius
    rectangles = [initial_bounds]
    first = validate(initial_body)["fp"] if initial_body is not None else []
    rows = list(first)
    report["scan_windows"] = [{"bounds": initial_bounds, "valid_rows": len(first),
                               "assumed_empty": initial_body is None}]
    report["minimum_drag_interval_seconds"] = MIN_INTERVAL_SECONDS
    report["max_quest_requests"] = MAX_QUEST_REQUESTS
    targets = plan(location, radius, initial_bounds)
    current = initial_bounds
    viewport = page.locator(".leaflet-container:visible").first
    box = viewport.bounding_box(timeout=3000)
    if not box:
        return "map_not_observed", None
    width, height = box["width"], box["height"]
    fixed_span = initial_bounds[1] - initial_bounds[3]
    handled = len(request_times)
    while not circle_coverage(rectangles, location, radius):
        if not targets:
            return "scan_coverage_incomplete", None
        target = targets[0]
        n, e, s, w = current
        # A target is reached only when the view center is within the overlap margin.
        if abs((n + s) / 2 - target["latitude"]) <= (n - s) * 0.02 and \
                abs((e + w) / 2 - target["longitude"]) <= (e - w) * 0.02:
            targets.pop(0)
            continue
        delta_x, delta_y = drag_delta(current, target, width, height)
        while monotonic() - request_times[-1] < MIN_INTERVAL_SECONDS:
            if restricted():
                return "scan_access_restricted", None
            page.wait_for_timeout(250)
        if restricted():
            return "scan_access_restricted", None
        before = len(request_times)
        if before != handled:
            return "scan_unexpected_requests", None
        if before >= MAX_QUEST_REQUESTS:
            return "scan_request_budget_reached", None
        x, y = box["x"] + width / 2, box["y"] + height * 0.47
        start_x, start_y = x - delta_x / 2, y - delta_y / 2
        distance = hypot(delta_x, delta_y)
        nudge_x, nudge_y = 6 * delta_x / distance, 6 * delta_y / distance
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        # Cross the map's click tolerance before applying the measured drag.
        page.mouse.move(start_x + nudge_x, start_y + nudge_y)
        page.mouse.move(start_x + nudge_x + delta_x, start_y + nudge_y + delta_y, steps=12)
        page.wait_for_timeout(200)
        page.mouse.up()
        outcome, bounds, body = next_response(before)
        if outcome not in {"valid_quests", "assumed_empty"}:
            return outcome, None
        handled = before + 1
        if bounds in rectangles:
            return "scan_view_did_not_move", None
        if abs((bounds[1] - bounds[3]) / fixed_span - 1) > 0.02:
            return "scan_zoom_changed", None
        current = bounds
        rectangles.append(bounds)
        batch = validate(body)["fp"] if body is not None else []
        rows.extend(batch)
        report["scan_windows"].append({"bounds": bounds, "valid_rows": len(batch),
                                       "assumed_empty": outcome == "assumed_empty"})
    report["scan_coverage_complete"] = True
    report["assumed_empty_windows"] = sum(window["assumed_empty"] for window in report["scan_windows"])
    if not rows:
        return "scan_no_valid_rows", None
    return "valid_quests", json.dumps({"fp": rows}).encode()
