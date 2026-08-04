import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_feeds", ROOT / "scripts" / "build_feeds.py"
)
build_feeds = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_feeds)


class BuildFeedsTests(unittest.TestCase):
    def test_example_file_builds_city_feeds(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            counts = build_feeds.build(
                ROOT / "examples" / "events.example.json",
                output,
                datetime.fromisoformat("2099-08-09T16:00:00+08:00"),
            )

            self.assertEqual(counts, {"all": 3, "current": 2, "archived": 1})
            hong_kong = json.loads(
                (output / "upcoming-hong-kong.json").read_text(encoding="utf-8")
            )
            self.assertEqual(hong_kong["count"], 1)
            self.assertEqual(hong_kong["events"][0]["status"], "ongoing")

    def test_city_prefix_must_match(self):
        invalid = {
            "id": "hk-2099-invalid",
            "title": "Invalid event",
            "city": "shenzhen",
            "start": "2099-01-01T10:00:00+08:00",
            "end": "2099-01-01T11:00:00+08:00",
            "venue": {"name": "Venue", "address": "Address"},
            "description": "Description",
            "source_url": "https://example.com/event",
            "last_verified": "2098-12-01",
        }

        with self.assertRaisesRegex(build_feeds.EventValidationError, "must begin"):
            build_feeds.validate_event(invalid, 0)

    def test_naive_time_is_rejected(self):
        with self.assertRaisesRegex(build_feeds.EventValidationError, "UTC offset"):
            build_feeds.parse_timestamp("2099-01-01T10:00:00", "start")


if __name__ == "__main__":
    unittest.main()
