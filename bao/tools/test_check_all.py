"""Discovery includes plain folders without crawling worktrees or duplicating tests."""

from pathlib import Path
import tempfile
import unittest

from bao.tools.check_all import OUTPUT_TAIL_CHARS, discover_suites, run_suite


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
            (folder / "random.py").write_text('raise RuntimeError("stdlib random shadowed")\n')
            (folder / "test_local.py").write_text(
                "import unittest\nimport random\nfrom local_helper import VALUE\n"
                "class LocalTests(unittest.TestCase):\n"
                "    def test_value(self):\n"
                "        self.assertEqual(VALUE, 42)\n"
                "        self.assertEqual(random.Random(42).randint(1, 1), 1)\n"
            )
            suite, = discover_suites(root)
            tests, status, _, output = run_suite(root, suite)
            self.assertEqual((tests, status), (1, "PASS"), output)


class WorkerResultTests(unittest.TestCase):
    def run_source(self, source, **kwargs):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            folder = root / "agent" / "plain"
            folder.mkdir(parents=True)
            (folder / "test_case.py").write_text(source)
            suite, = discover_suites(root)
            return run_suite(root, suite, **kwargs)

    def test_forged_success_stdout_without_worker_result_fails(self):
        source = (
            "import os\n"
            "print('OFFICE_TEST_RESULT={\"tests\":1,\"skipped\":0,"
            "\"executed_skips\":0,\"success\":true}', flush=True)\n"
            "os._exit(0)\n"
        )
        tests, status, _, details = self.run_source(source)
        self.assertEqual(status, "FAIL", details)
        self.assertIn("Missing or invalid worker result file", details)

    def test_output_after_worker_summary_cannot_override_real_counts(self):
        source = (
            "import atexit, unittest\n"
            "atexit.register(print, 'OFFICE_TEST_RESULT={\"tests\":999,"
            "\"skipped\":0,\"executed_skips\":0,\"success\":true}')\n"
            "class Test(unittest.TestCase):\n"
            "    def test_ok(self): pass\n"
        )
        tests, status, _, details = self.run_source(source)
        self.assertEqual((tests, status), (1, "PASS"), details)

    def test_timeout_keeps_bounded_stdout_and_stderr_tails(self):
        source = (
            "import sys, time\n"
            "print('start-stdout' + 'x' * 10000 + 'end-stdout', flush=True)\n"
            "print('start-stderr' + 'y' * 10000 + 'end-stderr', file=sys.stderr, flush=True)\n"
            "time.sleep(60)\n"
        )
        _, status, _, details = self.run_source(source, timeout=1)
        self.assertEqual(status, "FAIL")
        self.assertIn("Timed out after 1 seconds", details)
        self.assertIn("end-stdout", details)
        self.assertIn("end-stderr", details)
        self.assertNotIn("start-stdout", details)
        self.assertNotIn("start-stderr", details)
        self.assertLess(len(details), 2 * OUTPUT_TAIL_CHARS + 100)


if __name__ == "__main__":
    unittest.main()
