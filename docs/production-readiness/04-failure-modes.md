# 04 — Prioritized failure modes

Baseline commit `77d8754`. 22 findings. Each carries a concrete failure scenario, the evidence that
establishes it, and blast radius. Priorities:

- **P0** — blocks production use or represents an active security exposure.
- **P1** — will cause incorrect results or an outage under conditions that are expected to occur.
- **P2** — correctness or robustness defect requiring an uncommon trigger, or silent degradation.
- **P3** — hygiene, maintainability, or latent risk.

| ID | P | Title | Area |
|---|---|---|---|
| [F-01](#f-01--live-eodhd-credential-committed-to-a-public-repository) | P0 | Live EODHD credential committed to a public repository | Security |
| [F-02](#f-02--built-wheel-omits-the-fallback-calendar-data-file) | P0 | Built wheel omits the fallback calendar data file | Packaging |
| [F-03](#f-03--test-suite-fails-rather-than-skips-without-pyqlib) | P1 | Test suite fails rather than skips without pyqlib | Testing |
| [F-04](#f-04--requires-python-is-unbounded-but-pyqlib-097-caps-at-312) | P1 | `requires-python` unbounded, but pyqlib 0.9.7 caps at 3.12 | Packaging |
| [F-05](#f-05--dockerfile-smoke-test-runs-zero-tests) | P1 | Dockerfile "smoke test" runs zero tests | CI/CD |
| [F-06](#f-06--half-day-sessions-are-unmodelled-in-both-hours-and-the-eodhd-tier) | P1 | Half-day sessions unmodelled in both hours and the EODHD tier | Correctness |
| [F-07](#f-07--calendar-cache-writes-into-the-installed-package-directory) | P1 | Calendar cache writes into the installed package directory | Operability |
| [F-08](#f-08--register-before-qlibinit-ordering-is-unenforced) | P1 | `register()`-before-`qlib.init` ordering is unenforced | Contract |
| [F-09](#f-09--monkey-patch-does-not-reach-from-imported-references) | P2 | Monkey patch does not reach from-imported references | Correctness |
| [F-10](#f-10--reg_se-constant-patch-is-cosmetic) | P2 | `REG_SE` constant patch is cosmetic | Design |
| [F-11](#f-11--deal_priceadjusted_close-imposes-an-undeclared-data-contract) | P2 | `deal_price="adjusted_close"` imposes an undeclared data contract | Contract |
| [F-12](#f-12--global-state-mutation-without-locking-or-ownership-tracking) | P2 | Global state mutation without locking or ownership tracking | Concurrency |
| [F-13](#f-13--unregister-is-not-actually-best-effort) | P2 | `unregister()` is not actually best-effort | Robustness |
| [F-14](#f-14--dependency-floors-only-no-ceilings-no-lockfile) | P2 | Dependency floors only, no ceilings, no lockfile | Supply chain |
| [F-15](#f-15--eodhd-failures-are-swallowed-at-debug-level) | P2 | EODHD failures are swallowed at debug level | Observability |
| [F-16](#f-16--calendar-source-tier-varies-per-call-and-is-never-recorded) | P2 | Calendar source tier varies per call and is never recorded | Correctness |
| [F-17](#f-17--no-py-typed-lint-changelog-or-codeowners) | P3 | No `py.typed`, lint, CHANGELOG, or CODEOWNERS | Hygiene |
| [F-18](#f-18--normalize_symbol-is-lossy-for-swedish-share-classes-and-unused) | P3 | `normalize_symbol` is lossy for Swedish share classes and unused | Correctness |
| [F-19](#f-19--placeholder-package-metadata) | P3 | Placeholder package metadata | Hygiene |
| [F-20](#f-20--ci-has-no-matrix-lint-coverage-or-caching) | P3 | CI has no matrix, lint, coverage, or caching | CI/CD |
| [F-21](#f-21--a-third-of-the-package-is-outside-the-runtime-path-and-undocumented) | P3 | A third of the package is outside the runtime path and undocumented | Documentation |
| [F-22](#f-22--bus-factor-1-and-95-months-of-no-maintenance) | P3 | Bus factor 1 and 9½ months of no maintenance | Ownership |

---

## F-01 — Live EODHD credential committed to a public repository

**Priority:** P0 · **Area:** Security · **Evidence:** `pyproject.toml:43-44`,
[E-08](evidence-log.md#e-08--committed-credential-in-git-history)

`pyproject.toml` ends with a non-standard top-level table holding a literal EODHD API token
(redacted here; the value is at lines 43–44 of that file). It was introduced by commit `55327d9`
(2025-10-24) and is present at `HEAD` — approximately **9½ months of exposure** on a repository
whose remote is `https://github.com/maxilirator/qlib_ext_se.git`.

Two aggravating details:

1. **The credential is inert.** `config.get_eodhd_api_key()` (`config.py:31-47`) reads only the
   `EODHD_API_KEY` environment variable and `<config_dir>/config.toml`. Nothing in the package
   parses `pyproject.toml`. The token buys no functionality; it is pure exposure.
2. **Deleting it from `HEAD` does not remediate it.** The value remains reachable in git history
   and in any clone, fork, or cached view of the public repository.

*Failure scenario:* anyone with read access to the repository — or to any mirror, fork, or CI log
that echoed the file — extracts the token and consumes the account's EODHD quota, or uses it to
attribute requests to this account. Because the calendar path silently degrades to
`pandas_market_calendars` when EODHD fails (F-15), quota exhaustion caused by an abuser would
present as *nothing at all* to operators.

*Required action:* **rotate the token at EODHD first**, then remove the `[eodhd]` table, then purge
history or accept the exposure as permanent for the old value. Rotation is the only step that
changes the security posture. Not fixed here — this baseline is documentation-only; see
[`README.md` scope note](README.md#scope-note-on-the-approved-plan).

---

## F-02 — Built wheel omits the fallback calendar data file

**Priority:** P0 · **Area:** Packaging · **Evidence:** [E-05](evidence-log.md#e-05--wheel-contents)

`python -m build --wheel` produces a wheel containing the six `.py` modules and the `dist-info`
directory — and **not** `qlib_ext_se/data/xsto_trading_days_fallback.csv`. There is no `MANIFEST.in`,
no `[tool.setuptools.package-data]` table, and no `include-package-data` declaration, so setuptools
has no instruction to include the CSV.

Confirmed wheel contents:

```
qlib_ext_se/__init__.py   qlib_ext_se/calendar.py   qlib_ext_se/compat.py
qlib_ext_se/config.py     qlib_ext_se/defaults.py   qlib_ext_se/region.py
qlib_ext_se-0.1.0.dist-info/{licenses/LICENSE,METADATA,WHEEL,top_level.txt,RECORD}
```

*Failure scenario:* the consumer installs `qlib-ext-se` from a wheel or an artifact registry rather
than `pip install -e .`. `pandas_market_calendars` then fails for any reason — network-free build
image without the package, an incompatible pmc release, an exchange code lookup error — and
`build_xsto_trading_days` reaches `calendar.py:139`, finds no file at `_FALLBACK_CSV`, and
**re-raises the original exception**. The three-tier fallback advertised in `README.md:30` is
actually two tiers in every packaged install. The failure surfaces only when the other two tiers
are already down, i.e. exactly when it is needed.

*Fix:* add `[tool.setuptools.package-data] qlib_ext_se = ["data/*.csv"]`, then re-run the E-05
verification and confirm the CSV appears.

---

## F-03 — Test suite fails rather than skips without pyqlib

**Priority:** P1 · **Area:** Testing · **Evidence:** [E-03](evidence-log.md#e-03--test-suite-execution)

`pytest -q` on an environment without pyqlib gives **2 failed, 2 passed, 1 skipped**. Both failures
are `RuntimeError: pyqlib is not installed`, raised from `compat.py:18` via `region.py:107` and
`region.py:116`. `tests/test_register_basic.py` has no `importorskip` guard, unlike
`tests/test_dataset_smoke.py:7-10` which correctly uses `pytest.mark.skipif`.

*Failure scenario:* a contributor working on calendar logic — the half of the package that needs no
pyqlib — sees a red suite and cannot distinguish their own regression from the missing optional
dependency. Combined with F-04, this is not hypothetical: on any Python ≥3.13 the full suite is
*unrunnable as written*, so red is the only achievable state.

*Fix:* `pytest.importorskip("qlib")` at the top of `tests/test_register_basic.py`, so the suite
reports 2 passed / 3 skipped and states honestly what it covered.

---

## F-04 — `requires-python` is unbounded, but pyqlib 0.9.7 caps at 3.12

**Priority:** P1 · **Area:** Packaging · **Evidence:** [E-02](evidence-log.md#e-02--pyqlib-097-distribution-availability)

`pyproject.toml:10` declares `requires-python = ">=3.9"`. PyPI shows pyqlib 0.9.7 publishing **18
binary wheels spanning cp38–cp312 and no source distribution**. On CPython 3.13 the resolver
reports:

```
ERROR: Could not find a version that satisfies the requirement pyqlib==0.9.7 (from versions: none)
```

*Failure scenario:* a consumer on a current default Python (3.13 shipped in October 2024; 3.14 in
2025) adds `qlib-ext-se` to their dependencies. `pip` accepts the package's own metadata, then dies
resolving its hard-pinned transitive dependency with an error that names pyqlib rather than this
package. Diagnosis is slow because nothing points at the real constraint. This is the failure mode
that prevented the full test suite from running during this baseline.

*Fix:* `requires-python = ">=3.9,<3.13"`, and state the supported interpreter range in `README.md`.

---

## F-05 — Dockerfile "smoke test" runs zero tests

**Priority:** P1 · **Area:** CI/CD · **Evidence:** `Dockerfile:5-13`,
[E-09](evidence-log.md#e-09--pytest-exit-code-with-no-tests-collected)

`Dockerfile:12` comments `CMD ["pytest", "-q"]` as "Smoke test: calendar-only unit tests", but
`Dockerfile:5-6` copies only `pyproject.toml`, `README.md`, and `src/`. `tests/` never enters the
image. `pytest` with nothing to collect prints `no tests ran` and exits **5**.

*Failure scenario:* an operator runs the image expecting validation. Either the non-zero exit is
treated as a build/test failure and time is spent debugging working code, or the exit code is
ignored by a wrapper and a smoke test that never executed is recorded as green. Both outcomes are
worse than having no `CMD` at all.

*Fix:* either `COPY tests /app/tests` and keep the `CMD`, or delete the Dockerfile in line with the
advice already in `README.md:85` to install the extension into a single trainer image.

---

## F-06 — Half-day sessions are unmodelled in both hours and the EODHD tier

**Priority:** P1 · **Area:** Correctness · **Evidence:** `calendar.py:157-159`, `region.py:38-44`,
`calendar.py:90-103`, [E-06](evidence-log.md#e-06--xsto-regular-and-early-close-sessions)

XSTO runs abbreviated sessions several times a year. Verified for 2025 via
`pandas_market_calendars`:

| Date | Session | Regular close | Actual close |
|---|---|---|---|
| 2025-04-17 | Maundy Thursday | 17:30 | **13:00** |
| 2025-04-30 | Walpurgis Eve | 17:30 | **13:00** |
| 2025-05-28 | Day before Ascension | 17:30 | **13:00** |
| 2025-10-31 | All Saints' Eve | 17:30 | **13:00** |

Two independent defects follow:

1. **Minute grid.** `se_trading_hours()` returns a constant `("09:00:00", "17:30:00")`, and
   `_patch_time_utils` builds `SE_TIME` from it once at registration. `get_min_cal` therefore
   yields 510 minute slots on every session, over-stating each half-day by **270 minutes**. Any
   minute-frequency resampling, intraday index arithmetic, or `time_to_day_index` call on those
   dates is wrong. `time_to_day_index("14:00")` returns 300 for a session that closed at 13:00.
2. **EODHD tier.** `_generate_with_eodhd` treats **every** date returned by the holidays endpoint as
   a full closure (`calendar.py:102`), with no inspection of a type/`holidayType` field. EODHD's
   exchange-holidays feed commonly includes early-close entries. If it does for XSTO, tier 1 drops
   four real trading days from 2025 — days on which positions can be opened and closed.

*Failure scenario:* a bundle is generated with `EODHD_API_KEY` set. 2025-04-17 is absent from the
session list. Every downstream artefact — features, labels, backtest fills, live scheduling — treats
a live trading day as a market holiday. There is no test, no assertion, and no log line that would
surface this; the only signal is that the session count is four lower than PMC's.

*Note:* the currently committed fallback CSV does **not** exhibit this — it matches PMC exactly
(E-04), including all four half-days as present sessions. The risk is in the *preferred* tier and
in future regenerations.

---

## F-07 — Calendar cache writes into the installed package directory

**Priority:** P1 · **Area:** Operability · **Evidence:** `calendar.py:13,19-24,126,135`,
[E-03](evidence-log.md#e-03--test-suite-execution)

`_CACHE_DIR = os.path.join(os.path.dirname(__file__), "_cache")`. For an installed package that
resolves to `…/site-packages/qlib_ext_se/_cache/`, and `_ensure_cache_dir()` calls `os.makedirs` on
it at the top of every `build_xsto_trading_days` call — before any cache decision is made.

Four distinct problems:

- **Read-only or non-root containers.** `os.makedirs` raises `PermissionError`/`OSError`, which is
  *not* caught (`calendar.py:113` is outside every `try`). The function dies before it can consult
  any tier, including tiers that need no cache at all.
- **Source-tree pollution in development.** The test run created four files under
  `src/qlib_ext_se/_cache/`; `.gitignore:10` exists solely to hide them.
- **Unbounded growth with a degenerate key.** The cache key is the exact `(start, end)` pair. A
  one-day query caches a one-day file, so `is_trading_day` (`calendar.py:152-154`) writes **one CSV
  per date queried**. A loop over a year of dates produces ~365 files, none of which can serve any
  other query.
- **No TTL and no invalidation.** A cached range is authoritative forever, including a range built
  from a partial EODHD response.

*Failure scenario:* the extension is installed into a hardened trainer image running as a non-root
user with a read-only `/usr/lib/python3.12/site-packages`. The first calendar call raises
`PermissionError` from `os.makedirs`. Since the exception originates in cache setup rather than data
sourcing, the traceback points at a directory permission, not at a calendar problem.

*Fix:* resolve the cache root from `XDG_CACHE_HOME`/`platformdirs` with an explicit override
parameter, tolerate creation failure by degrading to no-cache, and key the cache by source tier.

---

## F-08 — `register()`-before-`qlib.init` ordering is unenforced

**Priority:** P1 · **Area:** Contract · **Evidence:**
[E-07](evidence-log.md#e-07--pyqlib-097-region-config-and-patch-target-analysis), `README.md:11-15`

pyqlib 0.9.7's `QlibConfig.set_region` performs `self.update(_default_region_config[region])` — an
unguarded dict index — and `qlib.init` calls it with the caller's `region`. If `register()` has not
run, `qlib.init(provider_uri=..., region='se')` raises `KeyError: 'se'`.

The ordering requirement exists only as prose in `README.md` and `INSTRUCTIONS.md`. There is no
guard, no import-time hook, no `qlib.init` wrapper, and no test asserting the failure mode.

*Failure scenario:* a refactor in the consumer moves `qlib.init` into an earlier bootstrap module,
or a lazily-imported code path calls `qlib.init` before the launcher's `register()`. The result is a
bare `KeyError: 'se'` from deep inside qlib's config layer, with nothing naming this extension. The
converse — importing `qlib.contrib.ops.high_freq` before `register()` — fails *silently* instead
(F-09).

*Fix:* export a `register_and_init(**kwargs)` convenience wrapper, or have `register()` raise a
clear error if `qlib.config.C` already reports an initialised state with an unknown region.

---

## F-09 — Monkey patch does not reach from-imported references

**Priority:** P2 · **Area:** Correctness · **Evidence:**
[E-07](evidence-log.md#e-07--pyqlib-097-region-config-and-patch-target-analysis)

`_patch_time_utils` rebinds module attributes on `qlib.utils.time`. Grepping the pyqlib 0.9.7 wheel
for the two patched names shows two classes of caller:

- **Patched successfully** — `qlib/utils/time.py` itself resolves `get_min_cal` through the module
  global at call time (`in_day_cal = get_min_cal(region=region)`, `cal = get_min_cal(C.min_data_shift, region)`).
- **Not patched** — `qlib/contrib/ops/high_freq.py` does `from qlib.utils.time import time_to_day_index`
  at module scope. Once that module is imported, its local binding points at the original function
  forever. That module additionally calls `time_to_day_index(self.start)` **without a `region`
  argument**, so it defaults to `REG_CN` and applies the Chinese session mapping irrespective of
  patch order.

*Failure scenario:* a consumer using high-frequency operators with SE data gets day indices computed
against the CN session (two sub-sessions, 240 minutes) rather than the SE session (510 minutes).
The computation succeeds and returns plausible integers; nothing raises. For daily-frequency work —
which is what `qlib-trading` appears to run — this is inert, which is why it ranks P2 rather than P1.

*Fix:* document that SE high-frequency operators are unsupported, and add an explicit unsupported
guard rather than leaving a silently-wrong path.

---

## F-10 — `REG_SE` constant patch is cosmetic

**Priority:** P2 · **Area:** Design · **Evidence:** `region.py:15-18`,
[E-07](evidence-log.md#e-07--pyqlib-097-region-config-and-patch-target-analysis)

`_monkey_patch_constants` sets `qlib.constant.REG_SE = "se"`. But `qlib/config.py` binds its region
constants with `from qlib.constant import REG_CN, REG_US, REG_TW` at import time and never performs
a dynamic lookup, so qlib itself can never observe `REG_SE`. The attribute is only visible to code
that reads `qlib.constant.REG_SE` directly — i.e. this package's own `region.py:52` and any
consumer that opts in.

It is harmless, but it creates a false impression that qlib has been extended at the constant level.
`INSTRUCTIONS.md:18` lists it as a registry to update, which reinforces the misconception.
`unregister()` also deletes the attribute unconditionally (`region.py:120-121`), which would remove
a natively-defined `REG_SE` if a future pyqlib ever adds one.

---

## F-11 — `deal_price="adjusted_close"` imposes an undeclared data contract

**Priority:** P2 · **Area:** Contract · **Evidence:** `region.py:30`,
[E-07](evidence-log.md#e-07--pyqlib-097-region-config-and-patch-target-analysis)

`qlib/backtest/exchange.py` normalises a string `deal_price` by prefixing `$` when absent, so this
setting resolves to the field **`$adjusted_close`** in the consumer's provider bundle. When
`get_deal_price` finds that field `None`, `NaN`, or `<= 1e-08`, the exchange logs
`setting deal_price to close price` at warning level and substitutes the close price.

The requirement is stated in `README.md:83` only as a bullet describing the default — never as a
precondition on the bundle. No test covers it; `tests/test_dataset_smoke.py` exercises `DatasetH`
and never constructs an exchange.

*Failure scenario:* a bundle is rebuilt without the `adjusted_close` field, or with the field named
differently. Backtests continue to run and produce results, silently priced at raw close instead of
adjusted close. Across dividends and splits the two diverge materially, so the strategy is evaluated
against prices it will not trade at. The only trace is a warning line per affected fill in the qlib
log.

*Fix:* document the bundle field requirement in this repository's README as contract C-4, and have
`qlib-trading`'s bundle validator assert `$adjusted_close` presence and non-nullity.

---

## F-12 — Global state mutation without locking or ownership tracking

**Priority:** P2 · **Area:** Concurrency · **Evidence:** `region.py:12,26,47-50,114-142`

`register()` mutates interpreter-global state — a module attribute, a module-level dict, and two
module-level functions — with no lock. `_ORIGINALS` is a bare module dict. Three consequences:

- Two threads racing `register()` can interleave the "capture original" and "install wrapper" steps.
  The capture is guarded by `if "get_min_cal" not in _ORIGINALS` (`region.py:47`) but that check and
  the later `setattr` (`region.py:81`) are not atomic together.
- `unregister()` pops `_default_region_config["se"]` and deletes `REG_SE` **unconditionally**, with
  no record of whether `register()` created them. If a second library or a future pyqlib defines
  either, this removes it.
- `unregister()` never clears `_ORIGINALS`, so the module retains references to the original
  functions indefinitely and a later `register()`/`unregister()` pair operates on a partially-stale
  record.

*Failure scenario:* a multiprocessing or thread-pool trainer where workers each call `register()`
during warm-up. The window is narrow and the symptom — one worker seeing an unpatched
`get_min_cal` — is a wrong minute grid rather than an exception.

*Fix:* guard `register`/`unregister` with a module-level `threading.Lock`, and record ownership
flags so rollback only reverses what this package installed.

---

## F-13 — `unregister()` is not actually best-effort

**Priority:** P2 · **Area:** Robustness · **Evidence:** `region.py:114-116`,
[E-03](evidence-log.md#e-03--test-suite-execution)

The docstring says "Best-effort rollback of monkey patches" and every subsequent block is wrapped in
`try/except: pass` — but the very first statement is `ensure_pyqlib_supported()`, which raises
`RuntimeError` when pyqlib is missing or its version differs. So the one function whose entire
design contract is "never fail" fails first, before reaching any of its own defensive handling.

This is directly observable: `test_unregister_is_noop_when_unregistered` fails for exactly this
reason.

*Failure scenario:* teardown code in a `finally:` block calls `unregister()` after an environment
problem has already occurred. The rollback raises, masking the original exception.

*Fix:* drop the version gate from `unregister()`, or wrap it in the same `try/except` as the rest.

---

## F-14 — Dependency floors only, no ceilings, no lockfile

**Priority:** P2 · **Area:** Supply chain · **Evidence:** `pyproject.toml:19-26`,
[E-01](evidence-log.md#e-01--environment)

Declared: `pyqlib==0.9.7` (exact), `pandas>=2.0`, `pandas-market-calendars>=4.3.2`,
`python-dateutil` (no constraint), `pytz` (no constraint), `requests>=2.31`. No upper bounds, no
lockfile, no `constraints.txt`, no dependabot configuration, and CI performs a fresh unpinned
resolve on every run.

The exact pyqlib pin combined with unbounded everything else is the worst of both worlds: the
component that would benefit from a range is frozen, and the components that need ceilings have
none. pyqlib 0.9.7 predates pandas 3.

Verified during this baseline: the **calendar** path works correctly on pandas 3.0.5 with
pandas-market-calendars 5.4.0 — both far outside the tested matrix, and both resolved automatically
by a fresh install today. The **registration** path is unverified against any pandas 3 combination
because pyqlib cannot be installed on the available interpreter (F-04).

*Failure scenario:* a CI run or a fresh deployment picks up a new pandas or pmc release that changes
`DatetimeIndex` or `schedule()` semantics. Because there is no lockfile, the same commit builds
green one day and red the next, with no diff to explain it.

*Fix:* add upper bounds (`pandas>=2.0,<4`, `pandas-market-calendars>=4.3.2,<6`), commit a
`constraints.txt` used by CI, and enable dependabot.

---

## F-15 — EODHD failures are swallowed at debug level

**Priority:** P2 · **Area:** Observability · **Evidence:** `calendar.py:52,85-87,98-99`

`_fetch_holidays_eodhd` wraps its entire body — request construction, HTTP call,
`raise_for_status`, JSON parse, and shape handling — in one `except Exception`, logs at **debug**
level, and returns `None`. `build_xsto_trading_days` then falls through to
`pandas_market_calendars` with no further signal. The inner per-date parse failures
(`calendar.py:71-72`, `calendar.py:82-83`) are `except Exception: pass` with no log at all.

Indistinguishable outcomes: no API key, an invalid API key, a 402 quota exhaustion, a network
timeout, a TLS failure, an EODHD schema change, and a genuinely empty holiday list. All produce the
same behaviour and, at default log level, the same silence.

*Failure scenario:* the credential in F-01 is abused and the account hits its quota. Every EODHD
call now 402s. Bundle regeneration silently switches from the EODHD tier to the PMC tier. Session
sets change, nobody is alerted, and the switch is not recorded in the cache file either (F-16).

*Fix:* log at warning level with the failure class, distinguish "no key configured" (info, expected)
from "key configured but call failed" (warning), and expose the resolved tier in the return value.

---

## F-16 — Calendar source tier varies per call and is never recorded

**Priority:** P2 · **Area:** Correctness · **Evidence:** `calendar.py:114-149`

`build_xsto_trading_days` can return sessions from four different sources, and the cache file it
writes is a bare `date` column with no provenance. Two specific inconsistencies:

- **Empty tier-1 results silently downgrade.** `calendar.py:122` requires `len(idx) > 0` to accept
  the EODHD result. A single-day query landing on a holiday legitimately returns zero sessions, so
  the code discards a correct answer and re-derives it from PMC. Adjacent queries in the same run
  can therefore be answered by *different* calendars — visible in the test run, where
  `xsto_2025-06-20_...csv` is a header-only file produced by the PMC branch while the neighbouring
  dates could have been produced by either.
- **Cache reads are provenance-blind.** `calendar.py:115-116` returns any cache hit regardless of
  which tier wrote it, whether an API key is now configured, or how old it is.

*Failure scenario:* a bundle build runs partly with a working EODHD key and partly after the key
starts failing. The resulting session list is a mixture of business-days-minus-holidays synthesis
and true XSTO schedule. Because the two agree on most dates (E-04 shows exact agreement for the
current CSV), the discrepancy is small, localised to a handful of dates, and effectively
undetectable after the fact.

*Fix:* write provenance into the cache (a `source` column or a sidecar JSON), accept empty tier-1
results as valid, and return the resolved tier to the caller.

---

## F-17 — No `py.typed`, lint, CHANGELOG, or CODEOWNERS

**Priority:** P3 · **Area:** Hygiene

Absent from the tree: `py.typed` (so the annotations throughout are invisible to consumers under
PEP 561), any lint or format configuration (no ruff/flake8/black/mypy settings), `CHANGELOG.md`,
`CODEOWNERS`, `MANIFEST.in`, `AGENTS.md`/`CLAUDE.md`, and any dependabot or release configuration.
The version string is duplicated between `pyproject.toml:7` and `__init__.py:10` with nothing
enforcing agreement.

---

## F-18 — `normalize_symbol` is lossy for Swedish share classes and unused

**Priority:** P3 · **Area:** Correctness · **Evidence:** `defaults.py:8-20`,
[E-12](evidence-log.md#e-12--normalize_symbol-behaviour)

`defaults.py:19` strips **all** hyphens, which destroys Swedish share-class notation:

| Input | Output | Exchange convention |
|---|---|---|
| `ERIC-B` | `ERICB.ST` | `ERIC-B.ST` |
| `VOLV-B.ST` | `VOLVB.ST` | `VOLV-B.ST` |
| `ATCO-A` | `ATCOA.ST` | `ATCO-A.ST` |

The function has **zero call sites** in this repository, including tests — yet `INSTRUCTIONS.md:21`
lists "symbol normalization helper provided in this extension" as a delivered registry item. An
unused, untested, incorrect helper that the hand-off document advertises is a trap for the next
integrator.

*Fix:* either correct it (preserve hyphens, add tests for the B/A share cases) or delete it and
remove the `INSTRUCTIONS.md` claim.

---

## F-19 — Placeholder package metadata

**Priority:** P3 · **Area:** Hygiene · **Evidence:** `pyproject.toml:12`

`authors = [{ name = "Your Team" }]` is unedited scaffolding, with no email and no maintainer field.
For a package intended for an artifact registry (`README.md:53`) there is no accountable contact in
the distribution metadata.

---

## F-20 — CI has no matrix, lint, coverage, or caching

**Priority:** P3 · **Area:** CI/CD · **Evidence:** `.github/workflows/ci.yml:1-23`

The single workflow runs one job on `ubuntu-latest` / Python 3.12: install, install pytest, run
pytest. Missing: an interpreter matrix (3.9–3.12 are all nominally supported, only 3.12 is
exercised), OS coverage (`pyproject.toml:17` claims OS independence; only Linux runs), pip caching,
any lint or type check, coverage measurement or gate, artifact upload, a build-and-verify-wheel step
that would have caught F-02, and concurrency control. It triggers on every push to every branch
while installing pyqlib and pandas uncached on each run.

---

## F-21 — A third of the package is outside the runtime path and undocumented

**Priority:** P3 · **Area:** Documentation · **Evidence:**
[E-11](evidence-log.md#e-11--internal-usage-of-de-facto-public-helpers)

`register()` consumes exactly one thing from `calendar.py`: `se_trading_hours()`. `build_xsto_trading_days`,
`is_trading_day`, the whole EODHD client, the cache, and the embedded CSV are **never reached** by
the runtime registration path — they are an offline bundle-generation utility. That is roughly 150
of 406 source lines.

No document says this. `README.md:19-31` presents the calendar section immediately after the
registration quick-start, and `INSTRUCTIONS.md:14` lists the calendar under "Region defaults",
inviting the reading that registering the region installs a Stockholm calendar into qlib. It does
not; qlib's trading days come from the provider bundle's `calendars/day.txt`. An integrator who
believes otherwise will not think to validate the bundle calendar.

---

## F-22 — Bus factor 1 and 9½ months of no maintenance

**Priority:** P3 · **Area:** Ownership · **Evidence:**
[E-10](evidence-log.md#e-10--repository-size-and-authorship)

Six commits, all on 2025-10-24, from one human identity (under two author strings) plus one
agent-authored commit. No commits between 2025-10-24 and this baseline on 2026-08-09, while the
package remains a hard runtime dependency of `qlib-trading` and hard-pins a pyqlib release. No
`CODEOWNERS`, no documented escalation path, no successor.
