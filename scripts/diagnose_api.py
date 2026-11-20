"""Classify an anonymous API response or a saved response body without exposing values."""
import argparse
import gzip
from http.client import HTTPException
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
import zlib

from probe_api import MAX_BYTES, ProbeError, StopRedirect, endpoint, validate

PUBLIC_ENDPOINT = "https://twpkinfo.com/getquest.ashx"
ERROR_MARKERS = {"error2", "沒有資料1！！"}
SAFE_TYPES = {"application/json", "application/octet-stream", "application/gzip",
              "text/html", "text/plain", "text/json"}


def classify(body, encoding):
    result = {"body_bytes": len(body)}
    if len(body) > MAX_BYTES:
        return {**result, "format": "unknown", "outcome": "response_too_large"}
    if body.startswith(b"\x1f\x8b") or encoding == "gzip":
        result["compression"] = "gzip"
        try:
            with gzip.GzipFile(fileobj=BytesIO(body)) as stream:
                body = stream.read(MAX_BYTES + 1)
        except (OSError, EOFError, zlib.error):
            return {**result, "format": "unknown", "outcome": "invalid_gzip"}
    elif encoding not in {"", "identity"}:
        return {**result, "format": "unknown", "outcome": "unsupported_encoding"}
    else:
        result["compression"] = "identity"
    result["decoded_bytes"] = len(body)
    if len(body) > MAX_BYTES:
        return {**result, "format": "unknown", "outcome": "response_too_large"}
    try:
        decoded = body.decode("utf-8-sig").strip()
        if decoded in ERROR_MARKERS:
            return {**result, "format": "text", "outcome": "error2"}
        if not decoded:
            return {**result, "format": "empty", "outcome": "empty_body"}
        if decoded.startswith("<"):
            return {**result, "format": "markup", "outcome": "non_json"}
        data = json.loads(decoded)
    except (ValueError, RecursionError):
        return {**result, "format": "unknown", "outcome": "invalid_json"}
    result["format"] = "json"
    rows = data.get("fp") if isinstance(data, dict) else None
    if isinstance(rows, list):
        result["fp_rows"] = len(rows)
        if any(isinstance(row, dict) and
               any(isinstance(row.get(key), str) and row[key] in ERROR_MARKERS for key in "ab")
               for row in rows):
            return {**result, "outcome": "error2"}
    try:
        validate(body)
    except ProbeError as error:
        return {**result, "outcome": str(error)}
    return {**result, "outcome": "valid_quests"}


def summarize_http(response):
    media_type = response.headers.get_content_type() if "Content-Type" in response.headers else ""
    encoding = response.headers.get("Content-Encoding", "").strip().lower()
    summary = {
        "http_status": response.code,
        "content_type": media_type if media_type in SAFE_TYPES else "other" if media_type else None,
        "content_encoding": encoding if encoding in {"gzip", "identity"} else "other" if encoding else None,
    }
    summary.update(classify(response.read(MAX_BYTES + 1), encoding))
    if response.code >= 400:
        summary["outcome"] = f"http_{response.code}"
    return summary


def anonymous():
    request = Request(endpoint(PUBLIC_ENDPOINT), headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": "pokemon-quest-map-probe/1.0",
    })
    try:
        try:
            response = build_opener(StopRedirect()).open(request, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            return summarize_http(response)
    except URLError as error:
        return {"outcome": "timeout" if isinstance(error.reason, TimeoutError) else "connection_error"}
    except TimeoutError:
        return {"outcome": "timeout"}
    except ProbeError as error:
        return {"outcome": str(error)}
    except (OSError, HTTPException):
        return {"outcome": "read_error"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--body", type=Path, help="an existing response body, with no request headers")
    mode.add_argument("--anonymous", action="store_true", help="make one anonymous GET")
    args = parser.parse_args()
    if args.body:
        try:
            with args.body.open("rb") as stream:
                result = classify(stream.read(MAX_BYTES + 1), "")
        except OSError:
            result = {"outcome": "file_read_error"}
        result.update(http_status=None, content_type=None, content_encoding=None)
    else:
        result = anonymous()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "valid_quests" else 1


if __name__ == "__main__":
    raise SystemExit(main())
