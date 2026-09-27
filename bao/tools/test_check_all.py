"""Discovery includes plain folders without crawling worktrees or duplicating tests."""

from pathlib import Path
import tempfile
import unittest

from bao.tools.check_all import discover_suites


class DiscoveryTests(unittest.TestCase):
    def test_packages_plain_folders_filter_and_stable_order(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            for name in (
                "zeta/__init__.py", "zeta/town/__init__.py", "zeta/town/test_z.py",
                "alpha/business/test_b.py", "alpha/business/test_a.py",
                "alpha/test_root.py", "alpha/empty/README.md",
                ".worktrees/copy/test_hidden.py", "alpha/.scratch/test_hidden.py",
                "alpha/business/deeper/test_nested.py",
            ):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            suites = discover_suites(root)
            self.assertEqual([suite.path.relative_to(root).as_posix() for suite in suites],
                             ["alpha", "alpha/business", "zeta/town"])
            self.assertEqual(suites[1].tests, ("test_a.py", "test_b.py"))
            self.assertEqual(discover_suites(root, "zeta"), [suites[2]])
            self.assertEqual(discover_suites(root, "unknown"), [])


if __name__ == "__main__":
    unittest.main()
