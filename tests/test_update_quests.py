import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_api import ProbeError
from update_quests import update


STATION = {"a": "station", "b": "補給站", "c": "22.1", "d": "120.1",
           "e": "task", "f": "reward", "g": "10"}


def body(*stations):
    return json.dumps({"fp": stations}).encode()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "quests.json"

    def test_valid_update_deduplicates_and_retains_timestamp_when_unchanged(self):
        newer = {**STATION, "g": "20"}
        self.assertEqual(update(self.path, body(newer, STATION)), ("updated", 1))
        saved = self.path.read_bytes()
        document = json.loads(saved)
        self.assertTrue(document["updated_at"].endswith("+00:00"))
        self.assertEqual(document["fp"][0]["g"], "20")
        self.assertEqual(update(self.path, body(STATION, newer)), ("unchanged", 1))
        self.assertEqual(self.path.read_bytes(), saved)

    def test_invalid_payload_preserves_previous_snapshot(self):
        update(self.path, body(STATION))
        saved = self.path.read_bytes()
        for payload in [
            b"error2", b'{"fp":[{"a":"error2"}]}', b'{"fp":[]}', b"{",
            body({**STATION, "b": " "}), body({**STATION, "d": -181}),
            body({**STATION, "e": ""}), body({**STATION, "f": ""}),
        ]:
            with self.subTest(payload=payload):
                with self.assertRaises(ProbeError):
                    update(self.path, payload)
                self.assertEqual(self.path.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
