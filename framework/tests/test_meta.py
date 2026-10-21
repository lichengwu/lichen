"""Unit tests for lib/meta.py — sidecar roundtrip, changelog, hashes.

These run entirely inside a temp directory: no repository state is touched.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import meta  # noqa: E402

SKILL_MD = """---
name: demo
description: Use when testing sidecar roundtrip behavior. 当需要测试 sidecar 读写时使用。
---

# demo

Trigger this skill when testing.
"""

SIDECAR = {
    "kind": "skill",
    "visibility": "private",
    "execution": "hybrid",
    "categories": ["coding"],
    "origin": "adopted",
    "generation": 1,
    "changelog": [],
}


def make_skill(tmp: Path, sid: str = "demo") -> Path:
    d = tmp / sid
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    return d


class TestSidecar(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lichen-meta-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        self.d = make_skill(self.tmp)

    def test_roundtrip(self):
        meta.write_sidecar(self.d, SIDECAR)
        got = meta.read_sidecar(self.d)
        self.assertEqual(got["visibility"], "private")
        self.assertEqual(got["categories"], ["coding"])

    def test_missing_sidecar_reads_empty(self):
        self.assertEqual(meta.read_sidecar(self.tmp / "demo"), {})

    def test_append_changelog_bumps_generation(self):
        m = dict(SIDECAR)
        m2 = meta.append_changelog(m, "first change")
        self.assertEqual(m2["generation"], 2)
        self.assertEqual(m2["changelog"][-1]["change"], "first change")

    def test_sha256_stable(self):
        a = meta.sha256_skill_md(self.d)
        b = meta.sha256_skill_md(self.d)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_categories_of_reads_sidecar(self):
        meta.write_sidecar(self.d, SIDECAR)
        skill = {"dir": self.d, "meta": meta.read_sidecar(self.d)}
        self.assertEqual(meta.categories_of(skill), ["coding"])


if __name__ == "__main__":
    unittest.main()
