"""Observe the quest page's own requests in one fresh Chromium context."""
import argparse
import json
import os
import sys
from time import monotonic
from urllib.parse import parse_qs, urlsplit

from diagnose_api import classify
from probe_api import MAX_BYTES, ProbeError, validate

PAGE = "https://twpkinfo.com/iquest.aspx"
ACCESS_STATUSES = {401, 403, 407, 429}
CHALLENGE = (
    'iframe[src*="recaptcha"][title*="challenge" i], '
    'iframe[src*="hcaptcha"][title*="challenge" i], '
    'iframe[src*="challenges.cloudflare.com"], '
    '#challenge-form, input[type="password"]'
)
ZOOM = '.leaflet-control-zoom-in, button[aria-label="Zoom in"], button[title="Zoom in"]'


def is_quest(url):
    parsed = urlsplit(url)
    return parsed.hostname == "twpkinfo.com" and parsed.path.lower() == "/getquest.ashx"


def quest_bounds(url):
    query = parse_qs(urlsplit(url).query)
    try:
        north, east, south, west = (float(query[key][0]) for key in "abcd")
    except (KeyError, ValueError):
        return None
    if -90 <= south < north <= 90 and -180 <= west < east <= 180:
        return north, east, south, west
    return None


def check_geolocation(page, location):
    return page.evaluate(
        """expected => new Promise(resolve => {
            if (!navigator.geolocation) {
                resolve('unavailable');
                return;
            }
            const timer = setTimeout(() => resolve('diagnostic_timeout'), 5000);
            const finish = status => {
                clearTimeout(timer);
                resolve(status);
            };
            navigator.geolocation.getCurrentPosition(({coords}) => {
                const matches = Math.abs(coords.latitude - expected.latitude) < 0.0001 &&
                    Math.abs(coords.longitude - expected.longitude) < 0.0001;
                finish(matches ? 'matches_configured_position' : 'different_position');
            }, error => {
                finish(({1: 'permission_denied', 2: 'position_unavailable', 3: 'timeout'})[error.code]
                    || 'unknown_error');
            }, {timeout: 3500, maximumAge: 0});
        })""",
        location,
    )


def geolocation_preflight(context, location):
    page = context.new_page()
    try:
        url = "http://127.0.0.1/questmap-geolocation-check"
        page.route(url, lambda route: route.fulfill(content_type="text/html", body="<!doctype html>"))
        page.goto(url, wait_until="domcontentloaded", timeout=5000)
        return check_geolocation(page, location)
    finally:
        page.close()


def analyze(response, on_valid=None):
    output = {"http_status": response.status, "valid_rows": 0}
    if response.status != 200:
        return {**output, "outcome": f"http_{response.status}"}
    content_length = response.header_value("content-length")
    if content_length and content_length.isdecimal() and int(content_length) > MAX_BYTES:
        return {**output, "outcome": "response_too_large"}
    # Chromium already decompresses the response body.
    body = response.body()
    summary = classify(body, "")
    output["outcome"] = summary["outcome"]
    if "fp_rows" not in summary:
        return output
    output["fp_rows"] = summary["fp_rows"]
    if summary["outcome"] == "valid_quests":
        output["valid_rows"] = output["fp_rows"]
        if on_valid:
            on_valid(body)
    elif summary["outcome"] == "invalid_row":
        for row in json.loads(body.decode("utf-8-sig"))["fp"]:
            try:
                validate(json.dumps({"fp": [row]}).encode())
            except ProbeError:
                continue
            output["valid_rows"] += 1
        if output["valid_rows"]:
            output["outcome"] = "valid_quests_with_invalid_rows"
    return output


def observe(browser, options, timeout_error, browser_error, report, on_valid):
    location = getattr(options, "location", None)
    context = browser.new_context(
        geolocation=location, permissions=["geolocation"], locale="zh-TW", timezone_id="Asia/Taipei"
    ) if location else browser.new_context()
    try:
        if location:
            report["stage"] = "geolocation_preflight"
            report["geolocation_preflight"] = geolocation_preflight(context, location)
            if report["geolocation_preflight"] != "matches_configured_position":
                return "browser_geolocation_preflight_failed"
        page = context.new_page()
        finished = []
        request_times = []
        blocked = []
        failed = []
        report["responses"] = []
        report["quest_requests"] = 0
        report["failed_script_requests"] = 0
        report["page_errors"] = 0
        report["off_target_responses"] = []
        report["unusable_bounds_responses"] = []
        report["failed_quest_requests"] = []

        def on_request(request):
            if is_quest(request.url):
                report["quest_requests"] += 1
                request_times.append(monotonic())

        def on_page_error(_error):
            report["page_errors"] += 1

        def on_response(response):
            if is_quest(response.url) and response.status in ACCESS_STATUSES:
                blocked.append(response.status)

        def on_finished(request):
            if is_quest(request.url):
                finished.append(request)

        def on_failed(request):
            if is_quest(request.url):
                failed.append(True)
                reason = request.failure or ""
                safe_reasons = {"net::ERR_ABORTED", "net::ERR_TIMED_OUT", "net::ERR_NAME_NOT_RESOLVED",
                                "net::ERR_CONNECTION_RESET", "net::ERR_CONNECTION_REFUSED",
                                "net::ERR_BLOCKED_BY_CLIENT", "net::ERR_FAILED"}
                report["failed_quest_requests"].append(reason if reason in safe_reasons else "other")
            elif request.resource_type == "script":
                report["failed_script_requests"] += 1

        page.on("request", on_request)
        page.on("pageerror", on_page_error)
        page.on("response", on_response)
        page.on("requestfinished", on_finished)
        page.on("requestfailed", on_failed)
        report["stage"] = "navigation"
        response = page.goto(PAGE, wait_until="domcontentloaded", timeout=25000)
        report["page_http_status"] = response.status if response else None
        if response and response.status in ACCESS_STATUSES:
            return "page_access_restricted"
        if not response or response.status >= 400:
            return "page_http_error"

        report["stage"] = "observation"
        def restricted():
            return blocked or any(locator.is_visible() for locator in page.locator(CHALLENGE).all())

        def next_scan_response(before):
            deadline = monotonic() + options.wait_seconds
            while monotonic() < deadline:
                if restricted():
                    return "scan_access_restricted", None, None
                if len(request_times) > before + 1:
                    return "scan_unexpected_requests", None, None
                if finished:
                    response = finished.pop(0).response()
                    bounds = quest_bounds(response.url) if response else None
                    if not bounds or len(request_times) != before + 1:
                        return "scan_invalid_bounds_or_request", None, None
                    bodies = []
                    result = analyze(response, bodies.append)
                    if not bodies:
                        report["scan_failure"] = {"bounds": bounds, **result}
                        return result["outcome"], None, None
                    return "valid_quests", bounds, bodies[0]
                if failed:
                    return "scan_request_failed", None, None
                page.wait_for_timeout(250)
            return "scan_response_timeout", None, None

        for may_zoom in (False, True) if options.zoom_once else (False,):
            if may_zoom:
                if not page.locator(ZOOM).first.is_visible():
                    report["interaction"] = "zoom_control_unavailable"
                    break
                page.locator(ZOOM).first.click(timeout=3000)
                report["interaction"] = "one_zoom_click"
            deadline = monotonic() + options.wait_seconds
            while monotonic() < deadline:
                if blocked:
                    report["responses"].append({"http_status": blocked[0], "valid_rows": 0})
                    return "api_access_restricted"
                if any(locator.is_visible() for locator in page.locator(CHALLENGE).all()):
                    return "visible_challenge_or_login"
                while finished:
                    quest_response = finished.pop(0).response()
                    if quest_response is None:
                        continue
                    if location:
                        bounds = quest_bounds(quest_response.url)
                        if bounds is None:
                            report["unusable_bounds_responses"].append(quest_response.status)
                            continue
                        north, east, south, west = bounds
                        if not (south <= location["latitude"] <= north and west <= location["longitude"] <= east):
                            report["off_target_responses"].append(
                                {"http_status": quest_response.status, "bounds": bounds}
                            )
                            continue
                        report["bounds"] = bounds
                    scan = getattr(options, "scan_radius", None)
                    bodies = []
                    result = analyze(quest_response, bodies.append if scan else on_valid)
                    report["responses"].append(result)
                    if result["valid_rows"] and (not location or result["outcome"] == "valid_quests"):
                        if scan:
                            from scan_area import sweep

                            report["stage"] = "scan"
                            outcome, body = sweep(page, options, report, bodies[0], bounds,
                                                  request_times, next_scan_response, restricted)
                            report["quest_request_intervals_seconds"] = [
                                round(second - first, 3) for first, second in zip(request_times, request_times[1:])
                            ]
                            if body is not None and on_valid:
                                on_valid(body)
                            return outcome
                        return "valid_quests"
                page.wait_for_timeout(250)
        if location:
            report["geolocation_permission"] = page.evaluate(
                "() => navigator.permissions.query({name: 'geolocation'}).then(result => result.state, () => 'unknown')"
            )
            if report["geolocation_permission"] == "granted":
                try:
                    report["geolocation_check"] = check_geolocation(page, location)
                except browser_error:
                    report["geolocation_check"] = "diagnostic_error"
        if report["responses"]:
            return "no_valid_quests"
        if report["off_target_responses"]:
            return "target_area_response_not_observed"
        if report["unusable_bounds_responses"]:
            return "quest_bounds_not_observed"
        if failed:
            return "quest_request_failed"
        return "quest_response_not_observed" if report["quest_requests"] else "quest_request_not_observed"
    except timeout_error:
        if report["stage"] == "geolocation_preflight":
            return "geolocation_preflight_timeout"
        return "navigation_timeout" if report["stage"] == "navigation" else "observation_timeout"
    except browser_error:
        if report["stage"] == "geolocation_preflight":
            return "geolocation_preflight_error"
        return "navigation_error" if report["stage"] == "navigation" else "observation_error"
    finally:
        context.close()


def run(options, on_valid=None):
    report = {"mode": "headed" if options.headed else "headless", "interaction": "none",
              "platform": sys.platform}
    try:
        from playwright.sync_api import Error, TimeoutError as BrowserTimeout, sync_playwright
    except ImportError:
        return {**report, "stage": "setup", "outcome": "playwright_not_installed"}
    if options.headed and sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        return {**report, "stage": "setup", "outcome": "no_graphical_display"}
    report["stage"] = "launch"
    use_shell = sys.platform.startswith("linux") and not options.headed and getattr(options, "location", None)
    report["browser_kind"] = "chromium_headless_shell" if use_shell else "chromium"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel=None if use_shell else "chromium", headless=not options.headed, timeout=15000
            )
            report["browser_version"] = browser.version
            try:
                report["outcome"] = observe(browser, options, BrowserTimeout, Error, report, on_valid)
            finally:
                browser.close()
    except (Error, OSError):
        report["outcome"] = "browser_launch_error" if report["stage"] == "launch" else "browser_error"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headed", action="store_true", help="show the Chromium window")
    parser.add_argument("--zoom-once", action="store_true", help="try one visible zoom-in click if needed")
    parser.add_argument("--wait-seconds", type=int, choices=range(1, 31), default=10, metavar="1..30")
    options = parser.parse_args()
    report = run(options)
    print(json.dumps(report))
    return 0 if report["outcome"] == "valid_quests" else 1


if __name__ == "__main__":
    raise SystemExit(main())
