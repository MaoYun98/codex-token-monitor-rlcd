import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources.codex_local import fetch_codex


class CodexLocalTests(unittest.TestCase):
    def test_reads_latest_limit_and_sums_latest_snapshot_per_task(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            sessions = home / "sessions" / "2026" / "07" / "16"
            sessions.mkdir(parents=True)
            self._write_snapshot(sessions / "one.jsonl", "2026-07-16T01:00:00Z", 40_000, 32)
            self._write_snapshot(sessions / "two.jsonl", "2026-07-16T02:00:00Z", 60_000, 37)

            usage = fetch_codex(home=home, now=datetime(2026, 7, 16, 3, tzinfo=timezone.utc))

            self.assertEqual(usage.today_tokens, 100_000)
            self.assertEqual(usage.latest_task_tokens, 60_000)
            self.assertEqual(usage.primary.label, "7d")
            self.assertEqual(usage.primary.remaining_percent, 63)
            self.assertEqual(usage.plan_type, "plus")

    def test_missing_session_data_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as temp:
            usage = fetch_codex(home=Path(temp), now=datetime.now(timezone.utc))
            self.assertEqual(usage.status, "unavailable")
            self.assertIsNone(usage.primary)

    @staticmethod
    def _write_snapshot(path: Path, timestamp: str, total_tokens: int, used_percent: int) -> None:
        event = {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"total_tokens": total_tokens},
                    "model_context_window": 258400,
                },
                "rate_limits": {
                    "primary": {
                        "used_percent": used_percent,
                        "window_minutes": 10080,
                        "resets_at": 1784789536,
                    },
                    "secondary": None,
                    "credits": {"balance": "0"},
                    "plan_type": "plus",
                },
            },
        }
        path.write_text(json.dumps(event) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
