"""Unit tests for lib/merge3.py — three-way text merge."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import merge3  # noqa: E402

BASE = "a\nb\nc\nd\ne\n"


class TestMergeText(unittest.TestCase):
    def test_no_change_returns_ours(self):
        merged, n = merge3.merge_text(BASE, BASE, BASE)
        self.assertEqual((merged, n), (BASE, 0))

    def test_disjoint_edits_both_survive(self):
        ours = "A\nb\nc\nd\ne\n"       # edit line 1
        theirs = "a\nb\nc\nd\nE\n"     # edit line 5
        merged, n = merge3.merge_text(BASE, ours, theirs)
        self.assertEqual(n, 0)
        self.assertIn("A", merged.splitlines())
        self.assertIn("E", merged.splitlines())

    def test_identical_edit_deduplicates(self):
        fix = "a\nB2\nc\nd\ne\n"
        merged, n = merge3.merge_text(BASE, fix, fix)
        self.assertEqual((merged, n), (fix, 0))

    def test_overlapping_different_edits_conflict(self):
        ours = "a\nOURS\nc\nd\ne\n"
        theirs = "a\nTHEIRS\nc\nd\ne\n"
        merged, n = merge3.merge_text(BASE, ours, theirs)
        self.assertEqual(n, 1)
        self.assertIn("<<<<<<< ours", merged)
        self.assertIn("=======", merged)
        self.assertIn(">>>>>>> theirs", merged)

    def test_theirs_only_change_adopts(self):
        theirs = "a\nb\nc\nd\nnew-tail\n"
        merged, n = merge3.merge_text(BASE, BASE, theirs)
        self.assertEqual(n, 0)
        self.assertIn("new-tail", merged)


if __name__ == "__main__":
    unittest.main()
