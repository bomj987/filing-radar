"""Тесты журнала событий. Пишут во временный файл, не трогают рабочий журнал."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filingradar.events import UnknownEvent, funnel, read, record  # noqa: E402


class TestRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "events.jsonl"

    def test_unknown_kind_is_rejected(self):
        # Опечатка в типе события тихо исказила бы всю воронку.
        with self.assertRaises(UnknownEvent):
            record("emails_sent", "FIRM", path=self.tmp)

    def test_event_is_appended_not_overwritten(self):
        record("report_generated", "A", path=self.tmp)
        record("email_sent", "A", path=self.tmp)
        self.assertEqual(len(read(self.tmp)), 2)

    def test_event_carries_timestamp_and_extra_fields(self):
        e = record("email_sent", "A", path=self.tmp, to="x@y.co.uk", findings=7)
        self.assertIn("ts", e)
        self.assertEqual(e["to"], "x@y.co.uk")
        self.assertEqual(json.loads(self.tmp.read_text().strip())["findings"], 7)

    def test_missing_file_reads_as_empty(self):
        self.assertEqual(read(self.tmp), [])


class TestFunnel(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "events.jsonl"

    def test_empty_funnel_has_no_fabricated_rates(self):
        f = funnel(self.tmp)
        self.assertEqual(f["emails_sent"], 0)
        self.assertIsNone(f["reply_rate_pct"])  # 0/0 — не ноль процентов, а «нет данных»

    def test_reply_rate_is_measured_against_delivered_not_sent(self):
        for i in range(10):
            record("email_sent", f"F{i}", path=self.tmp)
        record("email_bounced", "F0", path=self.tmp)
        record("email_bounced", "F1", path=self.tmp)
        record("reply_received", "F2", path=self.tmp)
        record("reply_received", "F3", path=self.tmp)
        f = funnel(self.tmp)
        self.assertEqual(f["delivered"], 8)
        self.assertEqual(f["reply_rate_pct"], 25.0)  # 2 из 8, а не 2 из 10

    def test_firms_touched_deduplicates(self):
        record("email_sent", "A", path=self.tmp)
        record("email_sent", "A", path=self.tmp)
        record("email_sent", "B", path=self.tmp)
        self.assertEqual(funnel(self.tmp)["firms_touched"], 2)


if __name__ == "__main__":
    unittest.main()
