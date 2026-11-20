import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest


ROOT = Path(__file__).resolve().parents[1]
ROW = {"b": "鳳山代天府", "c": "22.627163", "d": "120.372011", "e": "task", "f": "reward"}
SNAPSHOT = json.dumps({"fp": [ROW]}, ensure_ascii=False).encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status, encoding, data = self.server.reply
        self.send_response(status)
        if encoding:
            self.send_header("Content-Encoding", encoding)
        if status == 302:
            self.send_header("Location", "/do-not-follow")
        self.end_headers()
        self.wfile.write(data)
        self.server.requests += 1

    def log_message(self, *args):
        pass


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.requests = 0
        self.worker = Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.directory = tempfile.TemporaryDirectory()
        self.output = Path(self.directory.name) / "quests.json"
        self.previous = b"previous snapshot\n"
        self.output.write_bytes(self.previous)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.directory.cleanup()

    def probe(self, status, encoding, body, *args):
        self.server.reply = status, encoding, body
        url = f"http://127.0.0.1:{self.server.server_port}/feed?key=never-log-this"
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/probe_api.py"), "--output", str(self.output), *args],
            env={**os.environ, "QUEST_API_URL": url, "NO_PROXY": "127.0.0.1"},
            capture_output=True, text=True, timeout=10,
        )

    def test_plain_and_gzip_update(self):
        for encoding, body in [("", SNAPSHOT), ("gzip", gzip.compress(SNAPSHOT)), ("", gzip.compress(SNAPSHOT))]:
            with self.subTest(encoding=encoding, compressed=body != SNAPSHOT):
                result = self.probe(200, encoding, body)
                self.assertEqual(result.returncode, 0, result.stderr)
                saved = json.loads(self.output.read_bytes())
                self.assertEqual(saved["fp"][0]["b"], ROW["b"])

    def test_check_does_not_write(self):
        result = self.probe(200, "", SNAPSHOT, "--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), self.previous)

    def test_failed_response_preserves_file_and_redacts_input(self):
        for status, encoding, body, category in [
            (200, "", b"error2", "upstream_rejected"),
            (200, "", "沒有資料1！！".encode(), "upstream_rejected"),
            (200, "", b"<html>never-log-this</html>", "invalid_json"),
            (200, "", b"{}", "invalid_schema"),
            (200, "", b'{"fp":[]}', "empty_snapshot"),
            (200, "", b'{"fp":[{"c":91}]}', "invalid_row"),
            (200, "gzip", b"bad", "invalid_gzip"),
            (403, "", b"never-log-this", "http_403"),
            (429, "", b"never-log-this", "http_429"),
            (302, "", b"never-log-this", "redirect"),
        ]:
            with self.subTest(category=category):
                requests = self.server.requests
                result = self.probe(status, encoding, body)
                self.assertEqual(result.returncode, 1)
                self.assertIn(category, result.stderr)
                self.assertNotIn("never-log-this", result.stdout + result.stderr)
                self.assertEqual(self.output.read_bytes(), self.previous)
                self.assertEqual(self.server.requests, requests + 1)


if __name__ == "__main__":
    unittest.main()

