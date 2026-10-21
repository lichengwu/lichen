"""Unit tests for lib/taxonomy.py — keyword scoring, boundaries, normalize."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import taxonomy  # noqa: E402

TAX = {
    "coding": {"keywords": ["git", "code", "refactor"]},
    "office": {"keywords": ["excel", "document", "report"]},
    "design": {"keywords": ["design", "figma"]},
}


def skill(sid, name="", desc="", body=""):
    return {"id": sid, "fm": {"name": name, "description": desc}, "dir": None,
            "_body": body}


class TestClassify(unittest.TestCase):
    def test_head_hit_scores_double(self):
        # "git" in the id counts 2; desc hit adds 1 → coding wins
        s = skill("git-helper", desc="helpers for git workflows")
        cats = taxonomy.classify(s, TAX)
        self.assertEqual(cats[0], "coding")

    def test_desc_only_below_threshold_is_empty(self):
        # single desc hit = 1 < MIN_SCORE(2) → no guess
        s = skill("misc-tool", desc="mentions git once")
        self.assertEqual(taxonomy.classify(s, TAX), [])

    def test_body_reinforces_but_never_initiates(self):
        # head/desc silent; body full of "excel" → still no label
        s = skill("quiet-one", body="excel excel excel")
        self.assertEqual(taxonomy.classify(s, TAX), [])

    def test_ascii_prefix_boundary_excludes_digit(self):
        # \bgit matches "gitops" but must not match "digit"
        s = skill("digit-tools", desc="digit processing")
        self.assertEqual([c for c in taxonomy.classify(s, TAX) if c == "coding"], [])

    def test_multiple_categories_ranked(self):
        s = skill("code-report", desc="generate report from code review")
        cats = taxonomy.classify(s, TAX)
        self.assertIn("coding", cats)
        self.assertIn("office", cats)
        self.assertLessEqual(len(cats), taxonomy.MAX_LABELS)

    def test_empty_taxonomy_returns_empty(self):
        self.assertEqual(taxonomy.classify(skill("x", desc="git code"), {}), [])


class TestNormalize(unittest.TestCase):
    def test_unknown_labels_kept(self):
        # normalize keeps unknown labels (caller warns) rather than dropping
        kept, unknown = taxonomy.normalize(["coding", "not-a-cat"], TAX)
        self.assertIn("coding", kept)
        self.assertIn("not-a-cat", unknown)

    def test_matching_is_exact(self):
        # labels are matched exactly against the controlled vocabulary
        kept, unknown = taxonomy.normalize(["Coding"], TAX)
        self.assertEqual(kept, [])
        self.assertIn("Coding", unknown)


if __name__ == "__main__":
    unittest.main()
