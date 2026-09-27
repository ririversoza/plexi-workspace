"""Discovery includes plain folders without crawling worktrees or duplicating tests."""

from pathlib import Path
import tempfile
import unittest

from bao.tools.check_all import discover_suites, run_suite


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


class ImportPathTests(unittest.TestCase):
    def test_package_does_not_shadow_stdlib_inspect(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            package = root / "agent" / "town"
            package.mkdir(parents=True)
            (root / "agent" / "__init__.py").touch()
            (package / "__init__.py").touch()
            (package / "inspect.py").write_text('raise RuntimeError("stdlib inspect shadowed")\n')
            (package / "test_mock.py").write_text(
                "import unittest\nfrom unittest.mock import create_autospec\n"
                "class MockTests(unittest.TestCase):\n"
                "    def test_signature(self):\n"
                "        mock = create_autospec(lambda value: value)\n"
                "        mock(1)\n"
                "        mock.assert_called_once_with(1)\n"
            )
            suite, = discover_suites(root)
            tests, status, _, output = run_suite(root, suite)
            self.assertEqual((tests, status), (1, "PASS"), output)

    def test_plain_folder_keeps_local_imports(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            folder = root / "agent" / "business"
            folder.mkdir(parents=True)
            (folder / "local_helper.py").write_text("VALUE = 42\n")
            (folder / "test_local.py").write_text(
                "import unittest\nfrom local_helper import VALUE\n"
                "class LocalTests(unittest.TestCase):\n"
                "    def test_value(self): self.assertEqual(VALUE, 42)\n"
            )
            suite, = discover_suites(root)
            tests, status, _, output = run_suite(root, suite)
            self.assertEqual((tests, status), (1, "PASS"), output)


if __name__ == "__main__":
    unittest.main()
