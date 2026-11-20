"""Fetch a documented task endpoint and validate the snapshot before replacing it."""
import argparse
import gzip
from http import client
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zlib

from convert_data import number

MAX_BYTES = 16 * 1024 * 1024
FIELDS = "abcdefgh"


class ProbeError(Exception):
    """A fixed error category that is safe to write to a log."""


class StopRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError("redirect")


def endpoint(url):
    try:
        parsed = urlsplit(url)
        loopback = parsed.hostname in ("127.0.0.1", "::1", "localhost")
        allowed = parsed.scheme == "https" or (parsed.scheme == "http" and loopback)
        if allowed and parsed.hostname and parsed.username is None and not parsed.fragment:
            return url
    except (TypeError, ValueError):
        pass
    raise ProbeError("invalid_endpoint")


def read_response(url):
    try:
        request = Request(endpoint(url), headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": "pokemon-quest-map-probe/1.0",
        })
        # Each invocation issues one explicit request using a fresh opener.
        with build_opener(StopRedirect()).open(request, timeout=20) as response:
            content = response.read(MAX_BYTES + 1)
            encoding = response.headers.get("Content-Encoding", "").lower()
    except HTTPError as error:
        error.close()
        raise ProbeError(f"http_{error.code}") from None
    except (URLError, OSError, ValueError, client.HTTPException):
        raise ProbeError("connection_or_read_error") from None

    if len(content) > MAX_BYTES:
        raise ProbeError("response_too_large")
    if content.startswith(b"\x1f\x8b") or encoding == "gzip":
        try:
            with gzip.GzipFile(fileobj=BytesIO(content)) as stream:
                content = stream.read(MAX_BYTES + 1)
        except (OSError, EOFError, zlib.error):
            raise ProbeError("invalid_gzip") from None
    elif encoding not in ("", "identity"):
        raise ProbeError("unsupported_encoding")
    if len(content) > MAX_BYTES:
        raise ProbeError("response_too_large")
    return content


def validate(content):
    try:
        body = content.decode("utf-8-sig").strip()
        if body in {"error2", "沒有資料1！！"}:
            raise ProbeError("upstream_rejected")
        document = json.loads(body)
    except (ValueError, RecursionError):
        raise ProbeError("invalid_json") from None
    rows = document.get("fp") if isinstance(document, dict) else None
    if not isinstance(rows, list):
        raise ProbeError("invalid_schema")
    if not rows:
        raise ProbeError("empty_snapshot")

    validated = []
    for row in rows:
        if not isinstance(row, dict) or number(row.get("c"), 90) is None or number(row.get("d"), 180) is None:
            raise ProbeError("invalid_row")
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in "ef"):
            raise ProbeError("invalid_row")
        result = {}
        for key in FIELDS:
            value = row.get(key)
            if value is None or isinstance(value, str):
                result[key] = value
            elif key in "cdg" and number(value, 8640000000000) is not None:
                result[key] = value
        validated.append(result)
    return {"fp": validated}


def replace_snapshot(path, snapshot):
    encoded = json.dumps(snapshot, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing a file")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "quests.json")
    args = parser.parse_args()
    try:
        snapshot = validate(read_response(os.environ.get("QUEST_API_URL", "")))
        if not args.check:
            replace_snapshot(args.output, snapshot)
    except ProbeError as error:
        print(f"probe failed: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print("probe failed: output_error", file=sys.stderr)
        return 1
    print(f"{'validated' if args.check else 'updated'}: {len(snapshot['fp'])} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())

