"""Run office unittest suites in isolated temporary working directories."""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
MARKER = "OFFICE_TEST_RESULT="
WORKER = r'''
import json, pathlib, sys, unittest
root, folder = map(pathlib.Path, sys.argv[1:3])
sys.path.insert(0, str(root))
sys.path.insert(0, str(folder))
parts = folder.relative_to(root).parts
package = all((root.joinpath(*parts[:i]) / "__init__.py").is_file()
              for i in range(1, len(parts) + 1))
names = [(".".join(parts) + "." if package else "") + pathlib.Path(name).stem
         for name in sys.argv[3:]]
suite = unittest.defaultTestLoader.loadTestsFromNames(names)
result = unittest.TextTestRunner(verbosity=1).run(suite)
print("\nOFFICE_TEST_RESULT=" + json.dumps({"tests": result.testsRun,
      "skipped": len(result.skipped),
      "executed_skips": sum(isinstance(test, unittest.TestCase) for test, reason in result.skipped),
      "success": result.wasSuccessful()}))
sys.exit(0 if result.wasSuccessful() else 1)
'''


@dataclass(frozen=True)
class Suite:
    path: Path
    tests: tuple


def discover_suites(root, only=None):
    """Find direct agent tests and each immediate package, once, in sorted order."""
    suites = []
    for agent in sorted(root.iterdir()):
        if not agent.is_dir() or agent.is_symlink() or agent.name.startswith((".", "_")):
            continue
        if only is not None and agent.name != only:
            continue
        folders = [agent] + sorted(
            path for path in agent.iterdir()
            if path.is_dir() and not path.is_symlink() and not path.name.startswith((".", "_"))
        )
        for folder in folders:
            tests = tuple(sorted(path.name for path in folder.glob("test_*.py")
                                 if path.is_file() and not path.is_symlink()))
            if tests:
                suites.append(Suite(folder, tests))
    return suites


def run_suite(root, suite):
    started = time.monotonic()
    # Redirect both cwd writes and nested tempfile users into a disposable tree.
    with tempfile.TemporaryDirectory(prefix="plexi-check-", dir=os.environ.get("TMPDIR")) as scratch:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(root),
                   TMPDIR=scratch, TMP=scratch, TEMP=scratch)
        try:
            child = subprocess.run(
                [sys.executable, "-c", WORKER, str(root), str(suite.path), *suite.tests],
                cwd=scratch, env=env, capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            return "?", "FAIL", time.monotonic() - started, "Timed out after 120 seconds"
        records = [line[len(MARKER):] for line in child.stdout.splitlines()
                   if line.startswith(MARKER)]
        details = child.stdout + child.stderr
        try:
            result = json.loads(records[-1])
            tests, skipped = result["tests"], result["skipped"]
            success = child.returncode == 0 and result["success"]
            if not tests and not skipped:
                success = False
                details += "\nNo tests executed or explicitly skipped.\n"
            status = "FAIL" if not success else ("SKIP" if skipped and result["executed_skips"] == tests else "PASS")
            if skipped:
                status += f" ({skipped} skipped)"
        except (IndexError, KeyError, ValueError, TypeError):
            tests, status = "?", "FAIL"
        return tests, status, time.monotonic() - started, details


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="AGENT", help="Run only this agent's suites")
    args = parser.parse_args(argv)
    suites = discover_suites(ROOT, args.only)
    if not suites:
        parser.error("No test suites found" + (f" for agent {args.only!r}" if args.only else ""))
    print(f"{'Suite':<26} {'Tests':>6}  {'Result':<22} {'Seconds':>8}", flush=True)
    failures = []
    for suite in suites:
        tests, status, seconds, details = run_suite(ROOT, suite)
        name = suite.path.relative_to(ROOT).as_posix()
        print(f"{name:<26} {tests:>6}  {status:<22} {seconds:>8.2f}", flush=True)
        if status.startswith("FAIL"):
            failures.append((name, details))
    for name, details in failures:
        print(f"\n--- {name} failure output ---\n{details}", file=sys.stderr)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
