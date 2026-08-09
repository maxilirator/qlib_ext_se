# 03 — Reproducible setup, test, and run procedures

Baseline commit `77d8754`. Every procedure below was executed against this checkout on
2026-08-09 unless a step is explicitly marked *not executed*, with the reason given. Raw output is
in [`evidence-log.md`](evidence-log.md).

## 0. Supported platform matrix (derived, not declared)

| Component | Declared | Actually supported | Source |
|---|---|---|---|
| CPython | `>=3.9` (`pyproject.toml:10`) | **3.9 – 3.12** | pyqlib 0.9.7 publishes cp38–cp312 wheels and **no sdist** ([E-02](evidence-log.md#e-02--pyqlib-097-distribution-availability)) |
| pyqlib | `==0.9.7` (`pyproject.toml:20`) | `0.9.7` exactly | `compat.py:7` |
| pandas | `>=2.0` (`pyproject.toml:21`) | ≥2.0; calendar path verified working on **3.0.5** | [E-01](evidence-log.md#e-01--environment), [E-03](evidence-log.md#e-03--test-suite-execution) |
| pandas-market-calendars | `>=4.3.2` | verified working on **5.4.0** | [E-04](evidence-log.md#e-04--embedded-calendar-vs-pandas-market-calendars-xsto) |
| OS | "OS Independent" | Linux/macOS/Windows wheels exist for all pinned deps | `pyproject.toml:17` |

**Correct the declaration to `requires-python = ">=3.9,<3.13"`** — see F-04. On Python 3.13,
`pip install -e .` cannot resolve `pyqlib==0.9.7` at all; the observed error is
`ERROR: Could not find a version that satisfies the requirement pyqlib==0.9.7 (from versions: none)`.

## 1. Setup — full environment (what CI does)

```bash
git clone https://github.com/maxilirator/qlib_ext_se.git
cd qlib_ext_se
python3.12 -m venv .venv && . .venv/bin/activate      # 3.12 is the only version CI exercises
python -m pip install --upgrade pip
python -m pip install -e .                            # pulls pyqlib==0.9.7 + pandas + pmc + requests
python -m pip install pytest                          # NOT a declared dependency — see F-20
pytest -q
```

This mirrors `.github/workflows/ci.yml:15-23` exactly. Note that `pytest` is installed ad hoc in
both CI and the Dockerfile rather than declared as an optional dependency group; there is no
`[project.optional-dependencies]` table.

**Not executed in this baseline.** The environment available for this review is CPython 3.13.14,
on which `pyqlib==0.9.7` is uninstallable ([E-02](evidence-log.md#e-02--pyqlib-097-distribution-availability)).
This is itself a reproducibility finding, not merely an environment inconvenience: a contributor on
a current default Python cannot run the repository's own test suite as written. Rather than assert
an unverified pass, the registration path was analysed statically against the real pyqlib 0.9.7
wheel ([E-07](evidence-log.md#e-07--pyqlib-097-region-config-and-patch-target-analysis)).

## 2. Setup — calendar-only environment (no pyqlib)

This *is* what was executed, and it is the useful subset for anyone working on calendar logic:

```bash
python -m pip install "pandas>=2.0" "pandas-market-calendars>=4.3.2" pytest
PYTHONPATH=src pytest -q            # or plain `pytest -q`; pyproject.toml:41 sets pythonpath=["src"]
```

`pyproject.toml:41` sets `pythonpath = ["src"]`, so `pytest -q` from the repository root works
without any install at all — a genuinely convenient property worth preserving.

## 3. Test — observed results

```
$ PYTHONPATH=src python3 -m pytest -q -p no:cacheprovider
2 failed, 2 passed, 1 skipped in 0.82s
FAILED tests/test_register_basic.py::test_register_idempotent
FAILED tests/test_register_basic.py::test_unregister_is_noop_when_unregistered
```

| Test | Result here | Expected in full env | Notes |
|---|---|---|---|
| `test_calendar_dates.py::test_midsummer_eve_2025_closed` | **pass** | pass | 2025-06-20 correctly absent |
| `test_calendar_dates.py::test_random_open_days_around_midsummer_week` | **pass** | pass | 2025-06-18/19/23 correctly present |
| `test_register_basic.py::test_register_idempotent` | **fail** | pass | `RuntimeError: pyqlib is not installed` from `compat.py:18` |
| `test_register_basic.py::test_unregister_is_noop_when_unregistered` | **fail** | pass | same cause, via `region.py:116` |
| `test_dataset_smoke.py::test_dataset_smoke` | **skip** | skip | needs `SE_PROVIDER_URI` |

Two observations that are defects rather than environment artefacts:

- The registration tests **fail** rather than **skip** when pyqlib is unavailable. A
  `pytest.importorskip("qlib")` guard would make the suite honest about what it covered. (F-03)
- Running the suite **wrote four files into the source tree**, one per date the tests queried:

  ```
  src/qlib_ext_se/_cache/xsto_2025-06-18_2025-06-18.csv   16 bytes
  src/qlib_ext_se/_cache/xsto_2025-06-19_2025-06-19.csv   16 bytes
  src/qlib_ext_se/_cache/xsto_2025-06-20_2025-06-20.csv    5 bytes   (header only — the holiday)
  src/qlib_ext_se/_cache/xsto_2025-06-23_2025-06-23.csv   16 bytes
  ```

  `.gitignore:10` exists specifically to hide this. In an installed deployment the same writes land
  in `site-packages/qlib_ext_se/_cache/`. (F-07)

### Coverage reality

| Area | Covered by a test? |
|---|---|
| Embedded fallback CSV correctness | No — the passing calendar tests exercise the **PMC** tier, not the embedded tier |
| EODHD tier (`_generate_with_eodhd`, `_fetch_holidays_eodhd`) | **No test at all** — no fixture, no mock, no recorded response |
| Cache read/write/invalidations | No |
| `normalize_symbol` | No |
| `get_eodhd_api_key` resolution order | No |
| `se_trading_hours` | No |
| `deal_price` / exchange integration | No |
| Half-day sessions | No |
| Patch-before-`qlib.init` ordering | No |
| `register()` idempotency | Yes (blocked without pyqlib) |
| `DatasetH` end-to-end | Yes, but skipped by default |

The tier that is *preferred at runtime* — EODHD — has **zero** test coverage. That is the largest
single coverage gap.

## 4. Run — the container path

```bash
docker build -t qlib-ext-se .
docker run --rm qlib-ext-se
```

**This does not do what the Dockerfile says it does.** `Dockerfile:12` comments the `CMD` as
"Smoke test: calendar-only unit tests", but `Dockerfile:5-6` copies only `pyproject.toml`,
`README.md`, and `src/`. `tests/` is never present in the image, so `pytest -q` collects nothing
and exits **5** ([E-09](evidence-log.md#e-09--pytest-exit-code-with-no-tests-collected)). The
container therefore either fails for a reason unrelated to code quality, or — if the exit code is
not checked — reports a smoke test that never ran. (F-05)

`README.md:85` already advises omitting this Dockerfile and installing the extension into a single
trainer image instead, which is the sounder deployment story. The Dockerfile as it stands is a
liability rather than an asset: either fix it (`COPY tests /app/tests`) or delete it.

## 5. Run — library usage

```python
import qlib_ext_se
qlib_ext_se.register()          # MUST precede qlib.init; idempotent

import qlib
qlib.init(provider_uri="/path/to/se_bundle", region="se", logging_config=None)
```

Preconditions the caller must satisfy, none of which are checked by this package — see
[`02-cross-repository-interfaces.md` §5](02-cross-repository-interfaces.md#5-contract-imposed-on-the-qlib-trading-side)
for the full list (C-1 … C-8). The two most commonly missed: the bundle must carry
`$adjusted_close`, and the calendar in the bundle — not this package — determines qlib's trading
days.

## 6. Run — offline calendar generation

The package's other real use is producing a session list for bundle construction:

```python
from datetime import date
from qlib_ext_se.calendar import build_xsto_trading_days

days = build_xsto_trading_days(date(2000, 1, 3), date(2035, 12, 28), use_cache=False)
```

With no `EODHD_API_KEY` present this resolves via `pandas_market_calendars`. Verified: that output
matches the committed fallback CSV **exactly**, 9,041 sessions, zero divergence in either direction,
across the full 2000–2035 window
([E-04](evidence-log.md#e-04--embedded-calendar-vs-pandas-market-calendars-xsto)).

Caveats when using this for a real bundle:

- Pass `use_cache=False`, or the exact-`(start, end)` cache may return a stale set with no way to
  tell which tier produced it.
- The result is **session dates only**. Half-day sessions are indistinguishable from full sessions
  here, and the 09:00–17:30 window this package advertises is wrong on four dates in 2025
  ([E-06](evidence-log.md#e-06--xsto-regular-and-early-close-sessions)).
- If `EODHD_API_KEY` *is* set, you get the business-days-minus-holidays synthesis instead, which is
  a different and less faithful algorithm. Set the tier deliberately.

## 7. Verification commands for a reviewer

Fast, no pyqlib required, all executed for this baseline:

```bash
# 1. calendar tests
PYTHONPATH=src python -m pytest -q tests/test_calendar_dates.py

# 2. embedded CSV vs pandas-market-calendars, full window
python - <<'PY'
import csv, datetime, pandas as pd, pandas_market_calendars as mcal
emb = {datetime.date.fromisoformat(r["date"])
       for r in csv.DictReader(open("src/qlib_ext_se/data/xsto_trading_days_fallback.csv"))}
pmc = set(pd.DatetimeIndex(mcal.get_calendar("XSTO")
          .schedule(start_date="2000-01-01", end_date="2035-12-31").index).date)
print(len(emb), len(pmc), len(emb - pmc), len(pmc - emb))   # expect: 9041 9041 0 0
PY

# 3. does a built wheel carry the fallback CSV?
python -m build --wheel --outdir /tmp/whl
python -c "import zipfile,glob; print(*zipfile.ZipFile(glob.glob('/tmp/whl/*.whl')[0]).namelist(), sep='\n')"
#    expect (today): NO qlib_ext_se/data/... entry  -> F-02 reproduced

# 4. cache pollution
rm -rf src/qlib_ext_se/_cache && PYTHONPATH=src python -m pytest -q >/dev/null; ls src/qlib_ext_se/_cache
#    expect: four .csv files  -> F-07 reproduced
```

Cleanup afterwards: `rm -rf src/qlib_ext_se/_cache .pytest_cache build src/*.egg-info`. All four are
gitignored, and the working tree was confirmed clean after this baseline's evidence gathering
([E-13](evidence-log.md#e-13--working-tree-cleanliness)).
