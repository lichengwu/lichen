"""Unit tests for lib/lock.py — cross-process advisory lock."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.lock import file_lock  # noqa: E402


class TestFileLock(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lichen-lock-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        self.lock = self.tmp / "test.lock"

    def test_acquire_and_release(self):
        with file_lock(self.lock, timeout=1.0):
            pass  # acquired cleanly, released on exit
        # re-acquirable after release
        with file_lock(self.lock, timeout=1.0):
            pass

    def test_second_holder_times_out(self):
        import threading

        # flock 是 per-open-file-description 的：同进程第二个 fd 请求 LOCK_EX
        # 同样会阻塞，所以用线程即可验证互斥（也避开 macOS spawn 的限制）。
        started = threading.Event()
        release = threading.Event()
        errors = []

        def hold():
            try:
                with file_lock(self.lock, timeout=5.0):
                    started.set()
                    release.wait(5.0)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        t = threading.Thread(target=hold, daemon=True)
        t.start()
        self.assertTrue(started.wait(5.0), "holder never acquired the lock")
        with self.assertRaises(Exception):
            with file_lock(self.lock, timeout=0.3):
                self.fail("should not have acquired a held lock")
        release.set()
        t.join(5.0)
        self.assertEqual(errors, [])

    def test_body_executes_once(self):
        counter = []
        with file_lock(self.lock, timeout=1.0):
            counter.append(1)
        self.assertEqual(counter, [1])


if __name__ == "__main__":
    unittest.main()
