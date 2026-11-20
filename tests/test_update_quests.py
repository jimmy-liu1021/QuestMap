import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_api import ProbeError
from update_quests import covers_circle, filter_area, read_area, update


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

    def test_fengshan_probe_rejects_partial_bounds_and_filters_by_distance(self):
        self.path.write_text(
            '{"areas":[{"latitude":22.625,"longitude":120.35,"radius_km":10}]}',
            encoding="utf-8",
        )
        location, radius = read_area(self.path)
        self.assertEqual(radius, 10)
        self.assertFalse(covers_circle((22.638056, 120.377455, 22.611911, 120.322523), location, radius))
        self.assertTrue(covers_circle((22.8, 120.5, 22.4, 120.2), location, radius))
        near = {**STATION, "a": "near", "c": "22.625", "d": "120.35"}
        result = json.loads(filter_area(body(STATION, near), location, radius))
        self.assertEqual([station["a"] for station in result["fp"]], ["near"])


if __name__ == "__main__":
    unittest.main()
