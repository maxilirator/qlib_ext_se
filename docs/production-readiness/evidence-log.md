# Evidence log

Every command executed for this baseline, with its actual output. Assessed commit:
`77d8754` on `main`. Date: 2026-08-09.

**Environment.** Host interpreter is CPython 3.13.14, on which this package cannot be
installed (E-04). All execution therefore used a CPython 3.12.13 environment provisioned
with `uv`, matching CI (`.github/workflows/ci.yml:14`) and the `Dockerfile`
(`python:3.12-slim`).

**Isolation.** All environments, builds, and cache side effects were created under
`/workspace/artifacts/561823f4-…/`, never in the repository working tree. The only
modifications to the repository are the additions under `docs/production-readiness/`. No
network call was made to EODHD; the only network access was to PyPI (dependency resolution
and metadata) and GitHub (`gh`, read-only).

**Redaction.** The committed EODHD token is shown truncated. The full value is in
`pyproject.toml` and in git history; it is not reproduced here.

**Round-1 addendum (2026-08-09).** E-19, E-20 and E-21 were added after the initial
baseline, to make the cross-repository claims in
[02](02-cross-repository-interfaces.md) independently re-derivable. They pin the consumer
repository to an exact SHA and replace the earlier approximate coupling counts ("20+ call
sites") with an exhaustive enumeration. Runtime code is unchanged between the assessed
commit `77d8754` and the commit these were run against — `git diff --stat 77d8754 <HEAD> --
src tests pyproject.toml Dockerfile` is empty.

---

## E-01 — Repository visibility, CI history, open PRs

```console
$ gh repo view --json name,visibility,url
{"name":"qlib_ext_se","url":"https://github.com/maxilirator/qlib_ext_se","visibility":"PUBLIC"}

$ gh run list --limit 8
completed  success  docs: production-readiness baseline for qlib_ext_se   CI  agent/task-…  pull_request  1m17s  2026-08-09T18:39:17Z
completed  success  docs: add evidence-backed production-readiness baseline CI  agent/task-…  push          1m20s  2026-08-09T18:38:52Z
completed  success  Merge pull request #2 from maxilirator/chore/flatten…   CI  chore/flatten…  push        1m14s  2025-10-24T21:19:24Z
completed  success  Merge pull request #2 from maxilirator/chore/flatten…   CI  main            push        1m22s  2025-10-24T21:15:41Z
completed  success  chore(repo): flatten package to repository root…       CI  chore/flatten…  pull_request 2m27s  2025-10-24T21:13:12Z
completed  success  chore(repo): run CI from repo root, relocate README…   CI  chore/flatten…  push        1m30s  2025-10-24T21:10:02Z
completed  failure  chore(repo): flatten package to repository root…       CI  chore/flatten…  push          19s   2025-10-24T21:03:00Z
completed  failure  Running Copilot                                        Copilot          dynamic      14m28s  2025-10-24T18:52:48Z
```

Repository is **public**. CI is green on all recent runs. Substantive development is a
single day, 2025-10-24.

---

## E-02 — Environment provisioning and dependency footprint

```console
$ uv python install 3.12
Installed Python 3.12.13

$ uv venv -p …/cpython-3.12.13/bin/python3.12 .venv
$ uv pip install -e . pytest          # in a copy of the repo, outside the working tree

$ python -c "import importlib.metadata as md; print(len({d.metadata['Name'] for d in md.distributions()}))"
204

$ du -sh .venv
942M
```

Resolved versions of the direct dependencies and notable transitives:

```
pyqlib          0.9.7
pandas          2.3.3
numpy           2.5.2
python-dateutil 2.9.0.post0
pytz            2026.3.post1
requests        2.34.2
mlflow          3.15.1
scikit-learn    1.9.0
lightgbm        4.7.0
```

A 229-statement package resolves to 204 distributions and ~942 MB. Supports F-14.

---

## E-03 — Test suite, with declared dependencies present

```console
$ python -c "import qlib, sys; print('pyqlib', qlib.__version__); print('py', sys.version)"
pyqlib 0.9.7
py 3.12.13 (main, Mar 24 2026, 22:49:22) [Clang 22.1.1]

$ python -m pytest -q -p no:cacheprovider
..s..                                                                    [100%]
4 passed, 1 skipped
```

(Warnings omitted: `DeprecationWarning` for NumPy generic timedelta units, raised from
`exchange_calendars`, `pandas_market_calendars`, and `qlib.constant` — third-party, not
this package.)

**The suite is green.** A failure of `test_register_basic.py` with `RuntimeError: pyqlib is
not installed` indicates an incomplete environment — `pyqlib==0.9.7` is a mandatory
dependency at `pyproject.toml:20` — not a defect in the tests.

---

## E-04 — Interpreter support: `requires-python` vs. pyqlib wheel coverage

Available `pyqlib` 0.9.7 artifacts on PyPI:

```console
$ python -c "import urllib.request,json; d=json.load(urllib.request.urlopen('https://pypi.org/pypi/pyqlib/0.9.7/json')); print([f['filename'] for f in d['urls']])"
pyqlib-0.9.7-cp38-cp38-…  cp39-cp39-…  cp310-cp310-…  cp311-cp311-…  cp312-cp312-…
(manylinux2014_x86_64, macosx, win_amd64 — 18 wheels, NO sdist)
```

cp38–cp312 only, and no source distribution, so there is no build-from-source path.
Installing on CPython 3.13, which `requires-python = ">=3.9"` admits:

```console
$ uv venv -p /usr/local/bin/python3.13 .venv && uv pip install /workspace/…/qlib_ext_se
  And because only qlib-ext-se==0.1.0 is available and you require
  qlib-ext-se, we can conclude that your requirements are unsatisfiable.

  hint: You require CPython 3.13 (`cp313`), but we only found wheels for
  `pyqlib` (v0.9.7) with the following Python ABI tags: `cp38`, `cp39`,
  `cp310`, `cp311`, `cp312`
```

Supports F-05. The error names `pyqlib`, not this package, which is why this is easily
misdiagnosed as a test failure.

---

## E-05 — Committed EODHD credential: history and reachability

Present at `HEAD`:

```console
$ sed -n '43,44p' pyproject.toml
[eodhd]
api_key = "68ed7524…"        # redacted
```

Every commit in the repository containing the value, with the path it occupied:

```console
$ for c in $(git rev-list --all); do git grep -q '68ed7524…' $c && \
      echo "$(git log -1 --format='%h %ad %s' --date=short $c)" && git grep -l '68ed7524…' $c; done
77d8754 2025-10-24 Merge pull request #2 …            77d8754:pyproject.toml
1ac8000 2025-10-24 chore(repo): run CI from repo root  1ac8000:pyproject.toml
12438d4 2025-10-24 chore(repo): flatten package …      12438d4:pyproject.toml
5fdcc87 2025-10-24 docs: add child app usage guide     5fdcc87:ext/qlib-ext-se/pyproject.toml
55327d9 2025-10-24 feat(calendar): regenerate XSTO …   55327d9:ext/qlib-ext-se/pyproject.toml
```

Introduced in `55327d9`, **2025-10-24 22:38:41 +0200**, at `ext/qlib-ext-se/pyproject.toml`;
carried through the repository flattening to `pyproject.toml` at `HEAD`. Public since then
(E-01) — approximately 9.5 months as of this assessment.

Reachability from code:

```console
$ grep -rn "pyproject\|\[eodhd\]\|tool.eodhd" src/ tests/
src/qlib_ext_se/config.py:36:    2) TOML at <config_dir>/config.toml with key: [eodhd] api_key = "..."
```

The only match is a docstring. **Nothing in the package reads `pyproject.toml`**, so the
committed token is inert — it does not feed calendar tier 1.

**Not tested:** whether the token authenticates against EODHD. No request was made with it.
Exercising a third party's live credential is outside the read-only scope of this work and
would consume that account's quota. F-01 is scoped to what is verified — a committed,
publicly readable credential of unknown status — and its remediation (rotation) does not
depend on the answer.

---

## E-06 — Built wheel omits the calendar fallback data

```console
$ python -m build --wheel --no-isolation -o /tmp/wheelout .
Successfully built qlib_ext_se-0.1.0-py3-none-any.whl

$ python -c "import zipfile; [print(' ', n) for n in zipfile.ZipFile('/tmp/wheelout/qlib_ext_se-0.1.0-py3-none-any.whl').namelist()]"
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

CSV present in wheel: False
```

Six modules and metadata; no data file. Supports F-02.

---

## E-07 — Runtime consequence in a wheel-installed environment

Clean venv, wheel installed, tier 2 (`pandas-market-calendars`) forced to fail so the
last-resort tier is the one under test:

```python
import os, qlib_ext_se.calendar as cal
print("fallback path :", cal._FALLBACK_CSV)
print("fallback EXISTS:", os.path.exists(cal._FALLBACK_CSV))
cal._generate_with_pmc = lambda s, e: (_ for _ in ()).throw(RuntimeError("simulated PMC outage"))
cal.build_xsto_trading_days(date(2025,6,18), date(2025,6,24), use_cache=False)
```

```
fallback path : …/site-packages/qlib_ext_se/data/xsto_trading_days_fallback.csv
fallback EXISTS: False
RESULT: RAISED RuntimeError simulated PMC outage
```

The documented third tier (`README.md:30`) does not exist in a wheel install, and the
failure propagates instead of degrading. This is the install method the consumer's
Dockerfiles use (E-12). Supports F-02.

---

## E-08 — Embedded calendar vs. `pandas-market-calendars` XSTO: exact parity

```python
emb = cal._read_days_from_csv(cal._FALLBACK_CSV)
pmc = cal._generate_with_pmc(emb.min().date(), emb.max().date())
```

```
embedded rows: 9041 range: 2000-01-03 -> 2035-12-28
pmc rows     : 9041 range: 2000-01-03 -> 2035-12-28
in embedded not pmc: 0 []
in pmc not embedded: 0 []
```

**Zero divergence in either direction across 36 years.** The embedded snapshot is exactly
correct. Supports the "verified sound" table in [04](04-failure-modes.md) and F-18
(`README.md:30` calls this "a small audited window").

---

## E-09 — XSTO early closes vs. hardcoded trading hours

```python
x = mcal.get_calendar("XSTO")
s = x.schedule(start_date="2025-01-01", end_date="2025-12-31", tz="Europe/Stockholm")
```

```
se_trading_hours(): ('09:00:00', '17:30:00')
distinct local opens : ['09:00']
distinct local closes: ['13:00', '17:30']
early-close sessions in 2025: 4
    2025-04-17 09:00 -> 13:00
    2025-04-30 09:00 -> 13:00
    2025-05-28 09:00 -> 13:00
    2025-10-31 09:00 -> 13:00
```

Supports F-07.

---

## E-10 — `register()` / `unregister()` behaviour

```python
qlib_ext_se.register()
```

```
se minute-bar count/day: 510 first 09:00:00 last 17:29:00
actual half-day (09:00-13:00) minutes: 240
cn unaffected: 240
region config: {'trade_unit': 1, 'limit_threshold': None, 'deal_price': 'adjusted_close'}
after unregister, get_min_cal is original: True
REG_SE still present: False
```

Establishes four things at once: the region defaults match the documented contract (C-3);
non-`se` regions are untouched; `unregister()` restores the identical original function
object; and the SE minute grid is a fixed 510 bars regardless of the real session length
(F-07). Idempotency is covered by `test_register_basic.py` in E-03.

---

## E-11 — Cache location, per-date file growth, and read-only failure

```console
$ python -c "import qlib_ext_se.calendar as c, os; print(c._CACHE_DIR); print(os.listdir(c._CACHE_DIR))"
…/src/qlib_ext_se/_cache
inside package dir: True
['xsto_2025-06-20_2025-06-20.csv', 'xsto_2025-06-18_2025-06-18.csv',
 'xsto_2025-06-19_2025-06-19.csv', 'xsto_2025-06-23_2025-06-23.csv']
```

The four files are the residue of the four `is_trading_day` calls in
`tests/test_calendar_dates.py` — one file per queried date (F-12).

With the installed package directory made read-only, simulating a hardened container or a
root-owned `site-packages` under a non-root runtime user:

```console
$ chmod -R a-w …/site-packages/qlib_ext_se
$ python -c "…build_xsto_trading_days(date(2025,6,18), date(2025,6,24))"
RESULT: RAISED PermissionError [Errno 13] Permission denied:
'…/site-packages/qlib_ext_se/_cache/xsto_2025-06-18_2025-06-24.csv'
```

Supports F-03. Write permissions were restored immediately afterwards.

---

## E-12 — Consumer's pyqlib pins and install method

From the `qlib-trading` checkout available on disk during this assessment.

Dependency declaration (`pyproject.toml:11-14`):

```toml
dependencies = [
    "pyqlib>=0.9",
    "qlib-ext-se>=0.1.0",
```

arm64 image (`docker/Dockerfile.gpu.arm:57-60`) — the comment is the consumer's own:

```dockerfile
# Work around missing pyqlib==0.9.7 on arm64 by preinstalling a supported version,
# then install qlib_ext_se without deps.
ARG QLIB_VERSION=0.9.3
RUN pip install --no-cache-dir pyqlib==${QLIB_VERSION} \
    && pip install --no-cache-dir --no-deps "git+https://github.com/maxilirator/qlib_ext_se.git@main#egg=qlib_ext_se"
```

GPU image (`docker/Dockerfile.gpu:61-78`):

```dockerfile
# For full reproducibility, replace @main with a tag or commit SHA, e.g. @v0.1.0 or @<COMMIT_SHA>
RUN pip install --no-cache-dir "git+https://github.com/maxilirator/qlib_ext_se.git@main#egg=qlib_ext_se"
…
    x86_64) DEF="0.9.7" ;;
    aarch64|arm64) DEF="0.9.3" ;;
```

The same `aarch64→0.9.3` default appears in `Dockerfile.gpu.lite`,
`Dockerfile.app-gpu-wheel`, and `Dockerfile.app-gpu-wheel-cupybase`. `Dockerfile.cpu:24` and
`Dockerfile.oracle-continuation-cloud:35` correctly pin `pyqlib==0.9.7`.

Supports F-04, F-08, F-09.

---

## E-13 — The pyqlib version gate

`pyqlib` 0.9.3 publishes only cp37m/cp38 wheels and cannot be installed on 3.12:

```console
$ uv pip install "pyqlib==0.9.3"
  `pyqlib` (v0.9.3) with the following Python ABI tags: `cp37m`, `cp38`
```

The gate was therefore exercised directly. It is a membership test against a one-element
tuple (`compat.py:7,22-27`), so its behaviour is fully determined by the reported version:

```python
for v in ("0.9.3", "0.9.6", "0.9.8", "0.9.7"):
    qlib.__version__ = v; qlib_ext_se.register()
```

```
gate allows: ('0.9.7',)
  pyqlib 0.9.3: RAISED RuntimeError: qlib-ext-se supports pyqlib versions ('0.9.7',), found 0.9.3. Pin pyqlib==0.9.7 …
  pyqlib 0.9.6: RAISED RuntimeError: … found 0.9.6 …
  pyqlib 0.9.8: RAISED RuntimeError: … found 0.9.8 …
  pyqlib 0.9.7: register() OK
```

Combined with E-12: the consumer's arm64 images install 0.9.3, so `register()` raises at
runtime. Supports F-04.

---

## E-14 — `qlib-ext-se` is not published; pip constraint behaviour

```console
$ python -c "import urllib.request,json; json.load(urllib.request.urlopen('https://pypi.org/pypi/qlib-ext-se/json'))"
qlib-ext-se -> HTTPError 404
qlib_ext_se -> HTTPError 404
```

With 0.1.0 already installed from a wheel, the consumer's declared constraint resolves
without touching an index:

```console
$ pip install "qlib-ext-se>=0.1.0"
Requirement already satisfied: … (from … ->qlib-ext-se>=0.1.0)
```

The same constraint above the installed version fails hard:

```console
$ pip install "qlib-ext-se>=0.2.0"
ERROR: Could not find a version that satisfies the requirement qlib-ext-se>=0.2.0 (from versions: none)
ERROR: No matching distribution found for qlib-ext-se>=0.2.0
```

The consumer's build works only because the constraint floor equals the installed version.
Supports F-08.

---

## E-15 — Statement coverage

```console
$ python -m coverage run --source=src/qlib_ext_se -m pytest -q && python -m coverage report -m
Name                          Stmts   Miss  Cover   Missing
src/qlib_ext_se/__init__.py       3      0   100%
src/qlib_ext_se/calendar.py      92     52    43%   37-38, 43, 52-87, 97-103, 116, 121-127, 137-149
src/qlib_ext_se/compat.py        10      1    90%   24
src/qlib_ext_se/config.py        29      7    76%   16, 27-28, 40, 45-47
src/qlib_ext_se/defaults.py      12      7    42%   13-20
src/qlib_ext_se/region.py        83     21    75%   55-65, 68-76, 98-99, 122-123, 131-132, 141-142
TOTAL                           229     88    62%
```

Uncovered ranges of note: `calendar.py:52-87,97-103` (the whole EODHD tier),
`calendar.py:137-149` (the embedded-CSV tier), `region.py:55-76` (the bodies of both patched
functions — installed by the tests, never called), `defaults.py:13-20` (`normalize_symbol`).
Supports F-11.

---

## E-16 — `normalize_symbol`: extension vs. consumer

Both implementations imported into one process and applied to the same inputs:

```
  input                ext (qlib_ext_se)   consumer (q_train)
  'ERIC-B.ST'          'ERICB.ST'          'eric-b'
  'eric b'             'ERICB.ST'          'eric b'
  'VOLV-B'             'VOLVB.ST'          'volv-b'
  'ABB.XSTO'           'ABB.XSTO.ST'       'abb'
  ''                   ''                  ''
  '  Atco A .ST '      'ATCOA.ST'          'atco a '
```

Incompatible on case, suffix, and separator handling. The extension's handling of
`'ABB.XSTO'` is independently wrong — it strips only `.ST`, producing a double suffix.
Supports F-10.

---

## E-17 — Container image: the "smoke test" collects nothing

The `Dockerfile` build context reproduced exactly — `COPY pyproject.toml README.md /app/`
and `COPY src /app/src` (`Dockerfile:5-6`), with `tests/` absent — then its `CMD` run:

```console
--- files present in simulated image ---
./README.md
./pyproject.toml
./src/qlib_ext_se

--- CMD ["pytest","-q"] ---
(no output)
EXIT CODE: 5
```

Exit code 5 is pytest's "no tests collected". Supports F-06.

---

## E-18 — TOML credential path on Python 3.9/3.10

A valid `~/.config/qlib-ext-se/config.toml` containing `[eodhd] api_key = "SAMPLE-KEY"`,
read under both conditions of the guard at `config.py:6-9`:

```
3.11+ (tomllib present): SAMPLE-KEY
3.9/3.10 (tomllib None): None
```

`tomllib` is stdlib only from 3.11, and `_read_toml` returns `{}` when it is absent — so on
3.9 and 3.10, both inside the declared `requires-python = ">=3.9"` range, a valid credential
file is silently ignored. Supports F-17.

(`SAMPLE-KEY` is a placeholder written for this test; the committed token was not used.)

---

## E-19 — The consumer's complete coupling surface, at a pinned SHA

Every consumer-side citation in [02](02-cross-repository-interfaces.md) resolves against one
commit of `maxilirator/qlib-trading`:

```console
$ git -C <qlib-trading> rev-parse main
c8e7c4bcf6cd67daf55fe4102b53212fce072770
```

Exhaustive enumeration of the coupling, excluding documentation and the binary `profile.out`:

```console
$ git -C <qlib-trading> grep -lE 'import qlib_ext_se|import_module\("qlib_ext_se"\)' c8e7c4b -- '*.py' | wc -l
29
$ git -C <qlib-trading> grep -nE '\.register\(\)' c8e7c4b -- '*.py' | wc -l
30
$ git -C <qlib-trading> grep -lE '\.register\(\)' c8e7c4b -- '*.py' | wc -l
28
$ git -C <qlib-trading> grep -nE '\.unregister\(\)' c8e7c4b -- '*.py' | wc -l
0
$ git -C <qlib-trading> grep -nE 'qlib_ext_se\.(calendar|defaults|config|compat|region)|from qlib_ext_se import' c8e7c4b -- '*.py'
(no matches)
$ git -C <qlib-trading> grep -lE 'qlib_ext_se|qlib-ext-se' c8e7c4b -- 'docker/Dockerfile*' | wc -l
8
$ git -C <qlib-trading> ls-files c8e7c4b | grep -icE 'requirements.*\.txt|\.lock|constraints'
0
```

Every one of the 30 `.register()` matches is `qlib_ext_se.register()` or
`qles.register()` (verified: filtering those two spellings out leaves an empty set).

**Four facts follow, and they are what §5.4 of [02](02-cross-repository-interfaces.md)
rests on:**

1. The consumer imports `qlib_ext_se` in 29 modules and calls `register()` 30 times in 28 of
   them. (The 29th is `tests/test_qlib_data_connector.py:13`, a bare
   `pytest.importorskip("qlib_ext_se")`.)
2. `unregister()` has **zero** consumer call sites.
3. The consumer imports **no submodule** of this package and accesses **no attribute** other
   than `.register()`. The entire runtime contract is one nullary function.
4. Neither repository has a lock or constraints file, so nothing records which revision of
   this package any past build or run used.

This replaces the approximate "20+ call sites" figure used in the initial baseline.

---

## E-20 — `register()` reaches no calendar data tier and performs no I/O

The claim being tested: the missing wheel data file (E-06/E-07, F-02), the cache
`PermissionError` (E-11, F-03), and the divergent `normalize_symbol` (E-16, F-10) are all
present in the images the consumer builds, yet none of them can be triggered through
`register()` — the only entry point the consumer uses (E-19).

Run in the CPython 3.12.13 environment with the package installed, with every calendar data
tier replaced by a raiser **and** outbound sockets disabled:

```python
import socket
import qlib_ext_se.calendar as cal

def boom(*a, **k): raise AssertionError("calendar tier reached")
cal.build_xsto_trading_days = boom
cal.is_trading_day          = boom
cal._generate_with_pmc      = boom     # tier 2: pandas-market-calendars
cal._read_days_from_csv     = boom     # tier 3: embedded CSV
cal._fetch_holidays_eodhd   = boom     # tier 1: EODHD

_orig = socket.socket
class NoNet(_orig):
    def connect(self, *a, **k): raise AssertionError("network reached")
socket.socket = NoNet

import qlib_ext_se, qlib.config as qc, qlib.constant as qk
qlib_ext_se.register()
```

```
register() OK with all calendar data tiers and network sabotaged
REG_SE: se
se config: {'trade_unit': 1, 'limit_threshold': None, 'deal_price': 'adjusted_close'}
```

`register()` completes and installs the correct region configuration. The only calendar
symbol on its path is `se_trading_hours()` (`region.py:9` imports it; `calendar.py:157-159`
returns a hardcoded tuple with no I/O).

**Conclusion.** F-02, F-03 and F-10 are real and shipped, and are currently unreachable from
`qlib-trading` — contained by non-use, not by design. One import statement in the consumer
activates any of them. Also re-confirms C-3 independently of E-10.

---

## E-21 — Test suite re-run at the documentation commit

Confirming that the docs-only work in this round did not disturb the baseline recorded in
E-03, and that E-03 still reproduces:

```console
$ uv venv -p 3.12 .venv && uv pip install -e ./repo pytest
$ .venv/bin/python -c "import qlib,sys;print('pyqlib',qlib.__version__);print('py',sys.version.split()[0])"
pyqlib 0.9.7
py 3.12.13

$ .venv/bin/python -m pytest -q -p no:cacheprovider -W ignore::DeprecationWarning
..s..                                                                    [100%]
exit=0
```

4 passed, 1 skipped — unchanged from E-03. (The venv and a scratch copy of the repository
were created under `/workspace/artifacts/d9ae1c83-…/verify/`, never in the working tree; the
`-e` install therefore did not write a `_cache/` directory into the repository, cf. E-11 and
F-12.)
