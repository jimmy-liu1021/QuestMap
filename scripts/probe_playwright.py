"""Observe the quest page's own requests in one fresh Chromium context."""
import argparse
import json
import os
import sys
from time import monotonic
from urllib.parse import urlsplit

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
    context = browser.new_context()
    try:
        page = context.new_page()
        finished = []
        blocked = []
        failed = []
        report["responses"] = []

        def on_response(response):
            if is_quest(response.url) and response.status in ACCESS_STATUSES:
                blocked.append(response.status)

        def on_finished(request):
            if is_quest(request.url):
                finished.append(request)

        def on_failed(request):
            if is_quest(request.url):
                failed.append(True)

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
                    result = analyze(quest_response, on_valid)
                    report["responses"].append(result)
                    if result["valid_rows"]:
                        return "valid_quests"
                page.wait_for_timeout(250)
        if report["responses"]:
            return "no_valid_quests"
        return "quest_request_failed" if failed else "quest_response_not_observed"
    except timeout_error:
        return "navigation_timeout" if report["stage"] == "navigation" else "observation_timeout"
    except browser_error:
        return "navigation_error" if report["stage"] == "navigation" else "observation_error"
    finally:
        context.close()


def run(options, on_valid=None):
    report = {"mode": "headed" if options.headed else "headless", "interaction": "none"}
    try:
        from playwright.sync_api import Error, TimeoutError as BrowserTimeout, sync_playwright
    except ImportError:
        return {**report, "stage": "setup", "outcome": "playwright_not_installed"}
    if options.headed and sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        return {**report, "stage": "setup", "outcome": "no_graphical_display"}
    report["stage"] = "launch"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel="chromium", headless=not options.headed, timeout=15000
            )
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
