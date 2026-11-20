"""Plan fixed-zoom viewports locally from a measured quest query rectangle."""
import argparse
import json
from math import acos, asin, ceil, cos, degrees, radians, sin
from pathlib import Path

EARTH_RADIUS_KM = 6371


def circle_coverage(bounds, location, radius):
    """Check the full circle against the union, splitting at rectangle latitude edges."""
    lat, lng = location["latitude"], location["longitude"]
    angle = radius / EARTH_RADIUS_KM
    extent = degrees(angle)
    low, high = lat - extent, lat + extent
    peak = degrees(asin(sin(radians(lat)) / cos(angle)))
    edges = sorted({low, high} | {edge for n, _, s, _ in bounds for edge in (n, s) if low < edge < high})
    for south, north in zip(edges, edges[1:]):
        sample = radians(max(south, min(north, peak)))
        ratio = (cos(angle) - sin(radians(lat)) * sin(sample)) / (cos(radians(lat)) * cos(sample))
        half_span = degrees(acos(max(-1, min(1, ratio))))
        frontier = lng - half_span
        for west, east in sorted((w, e) for n, e, s, w in bounds if s <= south and north <= n):
            if west > frontier:
                break
            frontier = max(frontier, east)
            if frontier >= lng + half_span:
                break
        if frontier < lng + half_span:
            return False
    return True


def plan(location, radius, bounds):
    lat, lng = location["latitude"], location["longitude"]
    north, east, south, west = bounds
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("invalid viewport")
    # Reserve 5% of each measured span as overlap between adjacent cells.
    height = (north - south) * 0.95
    width = (east - west) * 0.95
    if min(height, width) < 0.001:
        raise ValueError("viewport is too small for this planner")
    angle = radius / EARTH_RADIUS_KM
    extent = degrees(angle)
    peak_latitude = degrees(asin(sin(radians(lat)) / cos(angle)))
    band_count = ceil(2 * extent / height)
    band_height = 2 * extent / band_count
    windows = []
    for band in range(band_count):
        low = lat - extent + band * band_height
        high = low + band_height
        sample = radians(max(low, min(high, peak_latitude)))
        ratio = (cos(angle) - sin(radians(lat)) * sin(sample)) / (cos(radians(lat)) * cos(sample))
        half_span = degrees(acos(max(-1, min(1, ratio))))
        cells = max(1, ceil(2 * half_span / width))
        step = 2 * half_span / cells
        centers = [lng - half_span + (index + 0.5) * step for index in range(cells)]
        if band % 2:
            centers.reverse()
        windows.extend({"latitude": (low + high) / 2, "longitude": center} for center in centers)
    return windows


def scan_plan(location, radius, bounds):
    windows = plan(location, radius, bounds)
    return {"center": location, "radius_km": radius, "measured_bounds": list(bounds),
            "planned_window_count": len(windows), "windows": windows}


def main():
    from update_quests import read_area

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--area-config", type=Path, default=Path("config/area.json"))
    parser.add_argument("--bounds", type=float, nargs=4, required=True, metavar="EDGE",
                        help="observed viewport, in north east south west order")
    args = parser.parse_args()
    location, radius = read_area(args.area_config)
    print(json.dumps(scan_plan(location, radius, args.bounds), indent=2))


if __name__ == "__main__":
    main()
