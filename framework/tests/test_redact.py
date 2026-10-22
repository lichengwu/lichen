"""Unit tests for lib/redact.py — hard pattern precision."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.redact import scan_text  # noqa: E402


class TestPhonePattern(unittest.TestCase):
    def test_real_phone_hits(self):
        hits = scan_text("联系人 13812345678 请勿外传", "t.md")
        self.assertEqual(len(hits), 1)

    def test_millisecond_timestamp_no_hit(self):
        # 13-digit epoch millis must not match the 11-digit phone pattern
        self.assertEqual(scan_text('"publishedAt": 1781935033901', "t.json"), [])
        self.assertEqual(scan_text('"ts": 1781935033901, "id": 1672531200000', "t.json"), [])

    def test_phone_inside_longer_digit_run_no_hit(self):
        self.assertEqual(scan_text("order 9138123456789 trace", "t.md"), [])

    def test_phone_at_line_edges_hits(self):
        for line in ("13812345678", "id=13812345678;", "(13812345678)"):
            self.assertEqual(len(scan_text(line, "t.md")), 1, line)


class TestOtherHardPatterns(unittest.TestCase):
    def test_email_hits(self):
        self.assertEqual(len(scan_text("mail me at foo.bar@qq.com", "t.md")), 1)

    def test_github_token_hits(self):
        self.assertGreaterEqual(
            len(scan_text("token ghp_" + "a" * 36, "t.md")), 1)

    def test_clean_text_no_hits(self):
        self.assertEqual(scan_text("just normal prose, nothing here", "t.md"), [])


if __name__ == "__main__":
    unittest.main()
