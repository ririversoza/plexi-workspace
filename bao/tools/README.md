# Office-wide test runner

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m bao.tools.check_all
PYTHONDONTWRITEBYTECODE=1 python3 -m bao.tools.check_all --only bao
```

The shorter `python3 -m bao.tools.check_all` also works. The environment prefix
additionally prevents Python from creating bytecode while importing the runner
itself; every suite subprocess always has `PYTHONDONTWRITEBYTECODE=1`.

Discovers immediate `<agent>/<package>/test_*.py` suites, including plain folders,
plus tests directly in an agent folder (such as Bao's roster). Hidden directories,
symlinks and deeper nested directories are excluded. Names are sorted; agent-root
tests do not recursively rerun package suites. `--only` matches an exact agent
name. No matching suites is an error, not a successful empty run.

Each suite runs in its own Python subprocess. Importable packages use qualified
module names, matching the READMEs' repository-root unittest discovery. Plain
folders use local module names, matching discovery without `-t .`. Package suites use only the repo root on the child import path, preventing
modules such as `mochi/tinytown/inspect.py` from shadowing the standard library.
Plain folders and legacy direct-agent suites (such as Bao's roster tests) also
place their own folder after standard-library paths but before installed packages
to support local imports such as `business`, `run` and `roster`. Each subprocess
keeps these local imports isolated from other suites.

Each child gets a fresh working directory under `$TMPDIR` (or the platform temp
directory when unset). Its `TMPDIR`, `TMP`, and `TEMP` point there too. Temporary
trees are removed on completion, failure or timeout. Output is captured in memory;
only failures print diagnostics. Timeout diagnostics preserve the last 4,000
characters of each captured stream, including byte output decoded safely. No run-output files are created in the repo.
This isolates ordinary relative and tempfile writes; it is not a sandbox against
a test explicitly writing to an absolute source path.

Worker counts and status are read from a result file inside the disposable
directory, never from stdout markers. Missing or malformed results fail closed;
a child exit code of zero alone is insufficient. This prevents ordinary test
output from forging success, but is not a security boundary against hostile
tests with access to the child process and filesystem.

The table reports suite, tests executed, PASS/FAIL/SKIP, skipped count when present,
and wall-clock seconds. An entirely skipped suite is SKIP; mixed passing/skipped
tests are PASS with a skip count. Import errors, failing tests, unexpected child
exit, no tests without explicit skips, and the 120-second per-suite timeout fail
the command. Exit status is 0 only when every suite passes or explicitly skips.

Discovery test: `python3 -m unittest bao.tools.test_check_all`.
