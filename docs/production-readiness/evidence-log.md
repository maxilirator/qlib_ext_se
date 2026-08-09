# Evidence log

Every command executed to produce this baseline, with observed output. Run on **2026-08-09** against
commit **`77d8754`** in `/workspace/runs/5110edba-9f19-4f28-855f-b0243185b4a7`.

All commands are read-only with respect to the repository. Three of them create ignored scratch
artefacts (`src/qlib_ext_se/_cache/`, `.pytest_cache/`, `build/`); all were removed afterwards and
the working tree was verified clean ([E-13](#e-13--working-tree-cleanliness)).

**No external service was mutated.** In particular, the EODHD credential found at
`pyproject.toml:43-44` was **deliberately not exercised** — validating a leaked token against the
live API would be an unauthorised use of someone's credential and would leave a request in their
account log. Its value is redacted throughout this documentation set; only its location is recorded.

---

## E-01 — Environment

```
$ python3 -V
Python 3.13.14

$ python3 -m pip install --user pandas "pandas-market-calendars>=4.3.2" pytest build
$ python3 -c "import pandas, pandas_market_calendars, pytest"
pandas                   3.0.5
pandas-market-calendars  5.4.0
pytest                   9.1.1
```

pyqlib is **not** installed and cannot be — see [E-02](#e-02--pyqlib-097-distribution-availability).
Note that pandas 3.0.5 and pmc 5.4.0 are both well above the declared floors (`>=2.0`, `>=4.3.2`),
which is what a fresh unpinned resolve produces today; this is the observation behind F-14.

---

## E-02 — pyqlib 0.9.7 distribution availability

```
$ python3 -m pip download pyqlib==0.9.7 --no-deps -d ./pyqlibdl
ERROR: Could not find a version that satisfies the requirement pyqlib==0.9.7 (from versions: none)
ERROR: No matching distribution found for pyqlib==0.9.7
```

PyPI metadata for the release:

```
$ python3 -c "<urllib fetch of https://pypi.org/pypi/pyqlib/json>"
latest: 0.9.7 | requires_python: >=3.8.0
0.9.7 files: 18
  pyqlib-0.9.7-cp310-cp310-{macosx_10_9_universal2, macosx_13_0_x86_64, manylinux_2_17_x86_64, win_amd64}.whl
  pyqlib-0.9.7-cp311-cp311-{macosx_10_9_universal2, manylinux_2_17_x86_64, win_amd64}.whl
  pyqlib-0.9.7-cp312-cp312-{macosx_10_13_universal2, manylinux_2_17_x86_64, win_amd64}.whl
  pyqlib-0.9.7-cp38-cp38-{macosx_11_0_universal2, macosx_13_0_x86_64, manylinux_2_17_x86_64, win_amd64}.whl
  pyqlib-0.9.7-cp39-cp39-{macosx_10_9_universal2, macosx_13_0_x86_64, manylinux_2_17_x86_64, win_amd64}.whl
0.9.7 requires_python values: ['>=3.8.0']
```

**18 binary wheels, cp38 – cp312, and no source distribution.** Python 3.13 has no installable
artifact, which is why the resolver reports `from versions: none`. Establishes **F-04**.

---

## E-03 — Test suite execution

```
$ PYTHONPATH=src python3 -m pytest -q -p no:cacheprovider
FAILED tests/test_register_basic.py::test_register_idempotent - RuntimeError: pyqlib is not installed...
FAILED tests/test_register_basic.py::test_unregister_is_noop_when_unregistered
2 failed, 2 passed, 1 skipped in 0.82s
```

Failure origin for both:

```
src/qlib_ext_se/region.py:116: in unregister
    ensure_pyqlib_supported()
src/qlib_ext_se/compat.py:18: RuntimeError
E   RuntimeError: pyqlib is not installed. Please install pyqlib==0.9.7 before using qlib-ext-se.
```

Side effect of the run — files created inside the source tree:

```
$ ls -la src/qlib_ext_se/_cache
-rw-r--r--  16  xsto_2025-06-18_2025-06-18.csv
-rw-r--r--  16  xsto_2025-06-19_2025-06-19.csv
-rw-r--r--   5  xsto_2025-06-20_2025-06-20.csv      # header only — the Midsummer Eve holiday
-rw-r--r--  16  xsto_2025-06-23_2025-06-23.csv
```

Establishes **F-03** (hard failure instead of skip), **F-07** (cache written into the package
directory, one file per queried date), and **F-13** (`unregister()` raising despite its best-effort
contract).

---

## E-04 — Embedded calendar vs pandas-market-calendars XSTO

```python
import csv, datetime, pandas as pd, pandas_market_calendars as mcal
emb = {datetime.date.fromisoformat(r["date"])
       for r in csv.DictReader(open("src/qlib_ext_se/data/xsto_trading_days_fallback.csv"))}
pmc = set(pd.DatetimeIndex(mcal.get_calendar("XSTO")
          .schedule(start_date="2000-01-01", end_date="2035-12-31").index).date)
```

```
embedded: 9041   pmc: 9041
in embedded not in PMC: 0
in PMC not in embedded: 0
2020-2026 embedded-only: []
2020-2026 pmc-only:      []
```

Independent data-quality checks on the same file:

```
weekend sessions in file: 0
sessions per year: 2000:251 2001:250 2002:250 2003:249 2004:253 2005:253 2006:251 2007:250
                   2008:252 2009:251 2010:253 2011:253 2012:250 2013:250 2014:249 2015:251
                   2016:253 2017:251 2018:250 2019:250 2020:252 2021:253 2022:253 2023:251
                   2024:251 2025:249 2026:251 2027:253 2028:251 2029:250 2030:250 2031:249
                   2032:254 2033:253 2034:251 2035:250

closure spot-checks (all correctly absent):
  2025-01-01, 2025-01-06, 2025-04-18, 2025-04-21, 2025-05-01, 2025-05-29, 2025-06-06,
  2025-06-20, 2025-12-24, 2025-12-25, 2025-12-26, 2025-12-31, 2024-03-29, 2024-12-24,
  2024-12-31, 2023-06-23, 2020-04-10, 2000-04-21, 2000-12-25
```

**Zero divergence across 36 years.** This is the strongest positive result in the baseline: the
embedded fallback is exact, correctly excludes Swedish-specific closures including Midsummer Eve,
Christmas Eve and New Year's Eve, and contains no weekend entries.

---

## E-05 — Wheel contents

```
$ python3 -m build --wheel --outdir <artifacts>/wheelcheck
Successfully built qlib_ext_se-0.1.0-py3-none-any.whl

$ python3 -c "import zipfile,glob; print(*zipfile.ZipFile(glob.glob('.../*.whl')[0]).namelist(), sep='\n')"
qlib_ext_se/__init__.py
qlib_ext_se/calendar.py
qlib_ext_se/compat.py
qlib_ext_se/config.py
qlib_ext_se/defaults.py
qlib_ext_se/region.py
qlib_ext_se-0.1.0.dist-info/licenses/LICENSE
qlib_ext_se-0.1.0.dist-info/METADATA
qlib_ext_se-0.1.0.dist-info/WHEEL
qlib_ext_se-0.1.0.dist-info/top_level.txt
qlib_ext_se-0.1.0.dist-info/RECORD
```

`qlib_ext_se/data/xsto_trading_days_fallback.csv` is **absent**. The build emitted no warning.
Establishes **F-02**.

---

## E-06 — XSTO regular and early-close sessions

```python
x = mcal.get_calendar("XSTO")
s = x.schedule(start_date="2025-01-01", end_date="2025-12-31")
x.early_closes(s)
```

```
tz: Europe/Stockholm | regular open/close: 09:00:00 17:30:00

XSTO 2025 early closes: 4
              market_open                market_close
2025-04-17    07:00:00+00:00 (09:00 CEST)  11:00:00+00:00 (13:00 CEST)
2025-04-30    07:00:00+00:00 (09:00 CEST)  11:00:00+00:00 (13:00 CEST)
2025-05-28    07:00:00+00:00 (09:00 CEST)  11:00:00+00:00 (13:00 CEST)
2025-10-31    08:00:00+00:00 (09:00 CET)   12:00:00+00:00 (13:00 CET)

normal week, 2025-06-16 … 2025-06-19: open 07:00Z (09:00), close 15:30Z (17:30)
```

Two conclusions. The constant returned by `calendar.py:157-159` — `("09:00:00", "17:30:00")` —
**matches** the XSTO regular session exactly. And there are **four dates in 2025 where it is wrong
by 4 hours 30 minutes**. Establishes the correct-hours positive finding and **F-06**.

---

## E-07 — pyqlib 0.9.7 region config and patch-target analysis

The cp312 manylinux wheel was downloaded for static inspection and **not installed**:

```
$ python3 -m pip download pyqlib==0.9.7 --no-deps --only-binary=:all: \
      --python-version 3.12 --implementation cp --abi cp312 \
      --platform manylinux_2_17_x86_64 -d ./qlibwhl
pyqlib-0.9.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
```

### `_default_region_config` shape — `qlib/config.py`

```python
_default_region_config = {
    REG_CN: {"trade_unit": 100,  "limit_threshold": 0.095, "deal_price": "close"},
    REG_US: {"trade_unit": 1,    "limit_threshold": None,  "deal_price": "close"},
    REG_TW: {"trade_unit": 1000, "limit_threshold": 0.1,   "deal_price": "close"},
}
```

The `"se"` entry injected at `region.py:27-31` — `trade_unit=1`, `limit_threshold=None`,
`deal_price="adjusted_close"` — matches this key shape exactly. **Positive finding.**

### Region resolution — `qlib/config.py`

```python
from qlib.constant import REG_CN, REG_US, REG_TW      # <- from-import; REG_SE is never consulted
...
def set_region(self, region):
    self.update(_default_region_config[region])       # <- unguarded index
...
self.set_region(kwargs.get("region", self["region"] if "region" in self else REG_CN))
```

Two findings: the `REG_SE` constant patch is invisible to qlib (**F-10**), and calling
`qlib.init(region='se')` before `register()` raises `KeyError: 'se'` from the unguarded index
(**F-08**).

### Patched-symbol callers — grep across every `.py` in the wheel

```
qlib/utils/time.py: def get_min_cal(shift: int = 0, region: str = REG_CN) -> List[time]:
qlib/utils/time.py: def time_to_day_index(time_obj: Union[str, datetime], region: str = REG_CN):
qlib/utils/time.py:     in_day_cal = get_min_cal(region=region)[:: freq.count]      <- module global, PATCHED
qlib/utils/time.py:     cal = get_min_cal(C.min_data_shift, region)[::sam_minutes]  <- module global, PATCHED

qlib/contrib/ops/high_freq.py: from qlib.utils.time import time_to_day_index        <- from-import, NOT PATCHED
qlib/contrib/ops/high_freq.py:     self.start_id = time_to_day_index(self.start) // self.data_granularity
qlib/contrib/ops/high_freq.py:     self.end_id   = time_to_day_index(self.end)   // self.data_granularity
```

The two internal callers inside `qlib/utils/time.py` resolve through the module global and therefore
see the patch. `qlib/contrib/ops/high_freq.py` binds the name at import time and additionally calls
it with **no `region` argument**, so it always uses `REG_CN`. Establishes **F-09**.

### `deal_price` handling — `qlib/backtest/exchange.py`

```python
if deal_price is None:
    deal_price = C.deal_price
if isinstance(deal_price, str):
    if deal_price[0] != "$":
        deal_price = "$" + deal_price
    self.buy_price = self.sell_price = deal_price
...
deal_price = self.quote.get_data(stock_id, start_time, end_time, field=pstr, method=method)
if method is not None and (deal_price is None or np.isnan(deal_price) or deal_price <= 1e-08):
    self.logger.warning(f"(stock_id:{stock_id}, trade_time:{(start_time, end_time)}, {pstr}): {deal_price}!!!")
    self.logger.warning(f"setting deal_price to close price")
    deal_price = self.get_close(stock_id, start_time, end_time, method)
```

`"adjusted_close"` resolves to the bundle field `$adjusted_close`; a missing or null value degrades
to close price with only a warning. Establishes **F-11**.

---

## E-08 — Committed credential in git history

```
$ git log --format="%h %ad %s" --date=short -S "<token-prefix>"
55327d9 2025-10-24 feat(calendar): regenerate XSTO fallback via EODHD; docs: add child app usage;
                   ext: se region defaults deal_price=adjusted_close; EODHD API key config

$ git log --oneline -S "<token-prefix>" -- pyproject.toml
12438d4 chore(repo): flatten package to repository root; ...
```

The literal token lives at `pyproject.toml:43-44` under a non-standard top-level `[eodhd]` table. It
entered history in `55327d9` on **2025-10-24**, survived the `12438d4` repository flatten, and is
present at `HEAD` — roughly **9½ months** of exposure on a public remote
(`https://github.com/maxilirator/qlib_ext_se.git`).

Confirmed inert: `config.get_eodhd_api_key()` (`config.py:31-47`) reads only `EODHD_API_KEY` and
`<config_dir>/config.toml`; a grep of `src/` finds no reference to `pyproject.toml`. The wheel build
in [E-05](#e-05--wheel-contents) succeeded without complaint, so setuptools silently ignores the
unknown table. Establishes **F-01**.

The token value is redacted from this documentation set, and it was not used against the EODHD API.

---

## E-09 — pytest exit code with no tests collected

```
$ cd <empty dir> && python3 -m pytest -q -p no:cacheprovider
no tests ran in 0.00s
EXIT=5
```

`Dockerfile:5-6` copies only `pyproject.toml`, `README.md`, and `src/` — `tests/` never enters the
image — so `CMD ["pytest", "-q"]` (`Dockerfile:13`) collects nothing and exits 5, despite the
comment at `Dockerfile:12` describing it as a calendar smoke test. Establishes **F-05**.

---

## E-10 — Repository size and authorship

```
$ git shortlog -sne --all
     4  Mattias Geisler <mattias@geisler.se>
     2  maxilirator <35955729+maxilirator@users.noreply.github.com>
     1  copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>

$ git log --oneline | wc -l
6
$ git log --format="%ad" --date=short | sort | sed -n '1p;$p'
2025-10-24
2025-10-24

$ wc -l src/qlib_ext_se/*.py tests/*.py
   10 __init__.py    159 calendar.py     27 compat.py     48 config.py
   20 defaults.py    142 region.py
   20 test_calendar_dates.py    34 test_dataset_smoke.py    26 test_register_basic.py
  486 total

$ git branch -a
* agent/task-49eeb3b6-5110edba
  main
  remotes/origin/HEAD -> origin/main
  remotes/origin/chore/flatten-ext-structure
  remotes/origin/copilot/create-qlib-ext-se-package
  remotes/origin/main
```

Entire history is six commits on a single day, from one human identity under two author strings plus
one agent commit. Establishes **F-22**.

---

## E-11 — Internal usage of de-facto public helpers

```
$ grep -rn "build_xsto_trading_days\|is_trading_day\|normalize_symbol\|get_eodhd_api_key\|se_trading_hours" \
       --include=*.py --include=*.md .
src/qlib_ext_se/region.py:9      from .calendar import se_trading_hours
src/qlib_ext_se/region.py:39         open_s, close_s = se_trading_hours()
src/qlib_ext_se/calendar.py:11   from .config import get_eodhd_api_key
src/qlib_ext_se/calendar.py:106  def build_xsto_trading_days(
src/qlib_ext_se/calendar.py:119      api_key = get_eodhd_api_key()
src/qlib_ext_se/calendar.py:152  def is_trading_day(dt: date) -> bool:
src/qlib_ext_se/calendar.py:153      idx = build_xsto_trading_days(dt, dt)
src/qlib_ext_se/calendar.py:157  def se_trading_hours() -> Tuple[str, str]:
src/qlib_ext_se/defaults.py:8    def normalize_symbol(symbol: str) -> str:
src/qlib_ext_se/config.py:31     def get_eodhd_api_key() -> Optional[str]:
tests/test_calendar_dates.py:3,9,20   (only test consumer)
```

`register()` reaches `calendar.py` through exactly one symbol, `se_trading_hours`.
`build_xsto_trading_days` has no runtime caller; `normalize_symbol` has **no caller at all**, not
even a test. Establishes **F-21** and the unused half of **F-18**.

---

## E-12 — normalize_symbol behaviour

```
$ PYTHONPATH=src python3 -c "from qlib_ext_se.defaults import normalize_symbol as n; ..."
'ERIC-B'     -> 'ERICB.ST'     # exchange convention: ERIC-B.ST
'ERIC-B.ST'  -> 'ERICB.ST'     # exchange convention: ERIC-B.ST
'eric b'     -> 'ERICB.ST'
'VOLV-B.ST'  -> 'VOLVB.ST'     # exchange convention: VOLV-B.ST
'ATCO-A'     -> 'ATCOA.ST'     # exchange convention: ATCO-A.ST
''           -> ''
'  ABB.st  ' -> 'ABB.ST'       # correct
```

`defaults.py:19` strips all hyphens, destroying Swedish share-class notation. Establishes **F-18**.

---

## E-13 — Working tree cleanliness

Scratch artefacts created during evidence gathering (`src/qlib_ext_se/_cache/`, `.pytest_cache/`,
`build/`, `src/*.egg-info`) were removed. Wheel and pyqlib downloads were written to the run's
artifact directory, outside the repository.

```
$ git status --porcelain
(no output before docs were written)
```

The only files added by this initiative are those under `docs/production-readiness/`. No runtime
code, configuration, dependency, credential, deployment state, or external service was modified.
