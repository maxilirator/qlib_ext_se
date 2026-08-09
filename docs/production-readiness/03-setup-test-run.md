# 03 — Reproducible setup, test, and run procedures

Every procedure below was executed against commit `77d8754` during this assessment. Raw
output is in [`evidence-log.md`](evidence-log.md). Nothing here is aspirational.

## 1. Prerequisites — read this first

**The interpreter choice is not free.** `pyqlib==0.9.7` is a mandatory dependency
(`pyproject.toml:20`) and publishes **wheels only for cp38–cp312, with no sdist** (E-04).
The package's own metadata says `requires-python = ">=3.9"` with no upper bound, so pip
will accept a newer interpreter and then fail to resolve:

```
hint: You require CPython 3.13 (`cp313`), but we only found wheels for
`pyqlib` (v0.9.7) with the following Python ABI tags: `cp38`, `cp39`, `cp310`, `cp311`, `cp312`
```

**Use Python 3.9–3.12.** CI uses 3.12 and the `Dockerfile` uses `python:3.12-slim`; 3.12 is
the only interpreter with direct evidence of a green run. Note that on 3.9 and 3.10 the
TOML credential path is silently inert because `tomllib` does not exist there (F-17, E-18
in `config.py:6-9`).

Footprint, for capacity planning: installing this 229-statement package pulls **204
distributions and ~942 MB**, because `pyqlib` transitively depends on mlflow, scikit-learn,
lightgbm and their stacks (E-02).

## 2. Setup

### 2.1 Development / editable (this is the only install with complete data)

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
pip install pytest
```

Verify:

```bash
python -c "import qlib, qlib_ext_se; print(qlib.__version__, qlib_ext_se.__version__)"
# expected: 0.9.7 0.1.0
```

### 2.2 Wheel / git install (what production actually does)

```bash
pip install "git+https://github.com/maxilirator/qlib_ext_se.git@main#egg=qlib_ext_se"
```

⚠️ **This install is incomplete.** It omits `data/xsto_trading_days_fallback.csv` (E-06),
so the last-resort calendar tier is absent at runtime (E-07). Until F-02 is fixed, verify
after any non-editable install:

```bash
python -c "
import os, qlib_ext_se.calendar as c
print('fallback present:', os.path.exists(c._FALLBACK_CSV))"
# currently prints: fallback present: False
```

Treat a `False` here as a failed install, not a warning.

### 2.3 Optional EODHD calendar credential

Only needed to exercise calendar tier 1. Resolution order (`config.py:31-48`):

1. `EODHD_API_KEY` environment variable
2. `~/.config/qlib-ext-se/config.toml` (or `%APPDATA%\qlib-ext-se\config.toml`), section
   `[eodhd] api_key = "..."`

The `[eodhd]` block in this repository's `pyproject.toml:43-44` is **not** one of these
paths and is read by nothing — see F-01.

## 3. Test

```bash
pytest -q            # addopts and pythonpath come from [tool.pytest.ini_options]
```

Result on Python 3.12 with dependencies installed (E-03):

```
..s..                                                                    [100%]
4 passed, 1 skipped
```

`pyproject.toml:39-41` sets `pythonpath = ["src"]`, so the suite runs against the source
tree without an install — but only if the third-party dependencies are present. **A failure
of `tests/test_register_basic.py` with `RuntimeError: pyqlib is not installed` means the
environment is incomplete, not that the code is broken.**

### 3.1 What the suite actually covers

| Test | Requires | Exercises |
|---|---|---|
| `test_register_basic.py::test_register_idempotent` | pyqlib | `register()` ×2, constants, region config |
| `test_register_basic.py::test_unregister_is_noop_when_unregistered` | pyqlib | `unregister()` ×2 |
| `test_calendar_dates.py` (2 tests) | pandas-market-calendars | tier 2 + cache write, 4 dates |
| `test_dataset_smoke.py` | `SE_PROVIDER_URI` | skipped by default — no CI job sets it |

Measured statement coverage (E-15):

```
Name                          Stmts   Miss  Cover
src/qlib_ext_se/__init__.py       3      0   100%
src/qlib_ext_se/calendar.py      92     52    43%
src/qlib_ext_se/compat.py        10      1    90%
src/qlib_ext_se/config.py        29      7    76%
src/qlib_ext_se/defaults.py      12      7    42%
src/qlib_ext_se/region.py        83     21    75%
TOTAL                           229     88    62%
```

62% overall, but the distribution matters more than the number:

- **Calendar tier 1 (EODHD), lines 52-87 and 97-103: 0% covered.** Every line of the
  network path — request construction, the two response-shape branches, the
  exception-swallowing handler, the business-day synthesis — is unexecuted by any test.
- **Calendar tier 3 (embedded CSV), lines 137-149: 0% covered.** The fallback that F-02
  shows is missing from wheels is also the fallback no test exercises. Both failures are
  invisible to the suite for the same reason.
- **`region.py:55-76`: 0% covered.** The bodies of the two patched functions,
  `get_min_cal_extended` and `time_to_day_index_extended`, are installed by the tests but
  never called by them.
- `defaults.py:13-20` — `normalize_symbol` — has no test at all.

The suite verifies that patching happens. It does not verify that the patched functions
behave correctly, nor that any calendar tier degrades as documented.

### 3.2 CI

`.github/workflows/ci.yml`: one job, `ubuntu-latest`, Python 3.12, `pip install -e .`,
`pytest -q`. Recent runs are green, including 1m17s–1m22s runs on 2026-08-09 (E-01).

CI is a valid environment, so its green status is meaningful — but narrow. It does not
build a wheel (so F-02 is invisible to it), does not lint or type-check, does not test any
other interpreter, does not exercise the container image, and installs unpinned transitive
dependencies fresh on every run.

## 4. Run

This package has no entry point, no CLI, and no service. "Running it" means calling it from
a host process:

```python
import qlib_ext_se
qlib_ext_se.register()          # idempotent; must precede qlib.init

import qlib
qlib.init(provider_uri="/path/to/xsto", region="se", logging_config=None)
```

Standalone calendar use, without pyqlib:

```python
from datetime import date
from qlib_ext_se.calendar import build_xsto_trading_days, is_trading_day

is_trading_day(date(2025, 6, 20))                              # False — Midsummer's Eve
build_xsto_trading_days(date(2025, 1, 1), date(2025, 12, 31))  # DatetimeIndex
```

`calendar.py` does not import pyqlib, so this works in an environment where only pandas and
`pandas-market-calendars` are installed.

### 4.1 Side effects of running

`build_xsto_trading_days` **writes into its own installation directory** —
`<package>/_cache/` (`calendar.py:13`). Consequences observed:

- In an editable install, cache CSVs appear inside `src/qlib_ext_se/_cache/` in the working
  tree. `.gitignore:10` covers this, so it does not dirty `git status`.
- The cache key is the `(start, end)` pair, so `is_trading_day` writes **one file per date
  queried**. A 4-date test run left 4 files (E-11).
- On a read-only or non-writable install location — the normal case for a hardened
  container or a root-owned `site-packages` under a non-root runtime user — the first
  calendar call raises (E-11):

  ```
  PermissionError: [Errno 13] Permission denied:
  '.../site-packages/qlib_ext_se/_cache/xsto_2025-06-18_2025-06-24.csv'
  ```

  This is raised from `_ensure_cache_dir()`/the cache write, not caught, and defeats all
  three fallback tiers. See F-03.

### 4.2 Container image

```bash
docker build -t qlib-ext-se .
docker run --rm qlib-ext-se
```

The image's `CMD ["pytest", "-q"]` is labelled "Smoke test: calendar-only unit tests"
(`Dockerfile:12`) but **runs zero tests**. `Dockerfile:5-6` copies only `pyproject.toml`,
`README.md`, and `src/`; `tests/` is never in the build context. Reproduced by building the
same file set locally and running the same command (E-17):

```
--- CMD ["pytest","-q"] ---
(no output)
EXIT CODE: 5
```

Exit code 5 is pytest's "no tests collected". A container smoke test that collects nothing
and exits non-zero is not a smoke test. See F-06.

## 5. Procedures that do not exist

For completeness, so no one assumes otherwise: there is no release procedure, no publish
step, no version-bump process, no lock file, no lint or format command, no type check, no
integration environment, and no documented rollback. See [05 — Operational gaps](05-operational-gaps.md).
