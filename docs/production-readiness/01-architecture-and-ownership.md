# 01 — Architecture and ownership boundaries

Baseline commit `77d8754`. All line references are to this checkout.

## 1. Physical inventory

The entire repository is 17 tracked files. Python and test source totals **486 lines**
([E-10](evidence-log.md#e-10--repository-size-and-authorship)).

| Path | Lines | Role |
|---|---:|---|
| `pyproject.toml` | 44 | setuptools build config, dependency floors, pytest config — **and a stray `[eodhd]` table (F-01)** |
| `Dockerfile` | 13 | `python:3.12-slim`, editable install, `CMD pytest -q` |
| `.github/workflows/ci.yml` | 23 | one job: Python 3.12, `pip install -e .`, `pytest -q` |
| `README.md` | 85 | user-facing docs, including the child-app integration guide |
| `INSTRUCTIONS.md` | 37 | hand-off checklist; reads as the original build spec |
| `LICENSE` | — | MIT |
| `.gitignore` | 219 | standard Python ignore set plus `src/qlib_ext_se/_cache/` (line 10) |
| `src/qlib_ext_se/__init__.py` | 10 | public API re-export; `__version__ = "0.1.0"` |
| `src/qlib_ext_se/region.py` | 142 | **all** qlib monkey-patching; `register()` / `unregister()` |
| `src/qlib_ext_se/calendar.py` | 159 | XSTO session sourcing, three-tier fallback, CSV cache, trading hours |
| `src/qlib_ext_se/config.py` | 48 | EODHD API-key resolution (env → user TOML) |
| `src/qlib_ext_se/compat.py` | 27 | pyqlib version gate |
| `src/qlib_ext_se/defaults.py` | 20 | `REGION_CODE` / `INDEX` / `CURRENCY`, `normalize_symbol` |
| `src/qlib_ext_se/data/xsto_trading_days_fallback.csv` | 9,042 | embedded sessions 2000-01-03 … 2035-12-28 |
| `tests/test_register_basic.py` | 26 | requires pyqlib; **fails hard without it** |
| `tests/test_calendar_dates.py` | 20 | pure calendar; passes without pyqlib |
| `tests/test_dataset_smoke.py` | 34 | skipped unless `SE_PROVIDER_URI` is set |

Absent from the tree: `AGENTS.md`, `CLAUDE.md`, `CODEOWNERS`, `CHANGELOG`, `MANIFEST.in`,
`py.typed`, any lint/format configuration, any dependency lockfile, any release workflow.

## 2. Import graph

```
qlib_ext_se/__init__.py
  └── region.py ──────────► compat.py      (importlib → qlib, version gate)
        │                 ► defaults.py    (REGION_CODE / INDEX / CURRENCY)
        └───────────────► calendar.py      (se_trading_hours ONLY)
                              └──────────► config.py   (EODHD key lookup)
```

The graph is acyclic and shallow. `calendar.py` imports `pandas` at module scope
(`calendar.py:8`), so `import qlib_ext_se` pulls pandas even for consumers that only want
`register()`. `pandas_market_calendars` and `requests` are imported lazily inside functions
(`calendar.py:28`, `calendar.py:53`), which is the right call for two heavy/optional dependencies.

`import qlib_ext_se` does **not** require pyqlib — `compat.py` only imports `qlib` when
`ensure_pyqlib_supported()` is actually called (`compat.py:16`).

## 3. Runtime path — what `register()` actually does

`register()` (`region.py:102-111`) performs four steps against the live interpreter:

| Step | Function | Target | Effective? |
|---|---|---|---|
| 1 | `_monkey_patch_constants` (`region.py:15`) | sets `qlib.constant.REG_SE = "se"` | **Cosmetic only.** `qlib/config.py` binds `REG_CN, REG_US, REG_TW` by from-import; qlib never reads `REG_SE`. (F-10) |
| 2 | `_patch_default_region_config` (`region.py:21`) | inserts `"se"` into `qlib.config._default_region_config` | **Load-bearing.** `QlibConfig.set_region` does `self.update(_default_region_config[region])`; without this, `qlib.init(region='se')` raises `KeyError`. |
| 3 | `_patch_time_utils` (`region.py:34`) | replaces `qlib.utils.time.get_min_cal` and `.time_to_day_index` | **Partially effective.** Internal callers in `qlib/utils/time.py` use module-global lookup and see the patch; `qlib/contrib/ops/high_freq.py` from-imports `time_to_day_index` at import time and does not. (F-09) |
| 4 | `_structured_info_log` (`region.py:85`) | one INFO line via `qlib.log` | Best-effort; all exceptions swallowed (`region.py:98-99`) |

Verified against the actual pyqlib 0.9.7 wheel in
[E-07](evidence-log.md#e-07--pyqlib-097-region-config-and-patch-target-analysis).

### Ordering contract

Because step 2 is load-bearing and `set_region` is called from `qlib.init`, **`register()` must run
before `qlib.init(region='se')`**. Nothing in the package enforces or detects violation of this
ordering; it exists only as prose in `README.md:11-15` and `README.md:69-75`. See F-08.

### Rollback

`unregister()` (`region.py:114-142`) reverses steps 1–3 on a best-effort basis, each in its own
`try/except: pass`. Three defects: it calls `ensure_pyqlib_supported()` first (`region.py:116`) and
therefore *raises* when pyqlib is absent (F-13); it removes `REG_SE` and the `"se"` region entry
unconditionally rather than only when `register()` created them; and it never clears `_ORIGINALS`
(F-12).

## 4. What this package owns — and what it does not

### Owns

- The `se` entry in pyqlib's region config, and its three values:
  `trade_unit=1`, `limit_threshold=None`, `deal_price="adjusted_close"` (`region.py:27-31`).
- The SE intraday minute grid: a single continuous 09:00–17:30 window, no lunch break
  (`region.py:38-44`, sourced from `calendar.py:157-159`).
- Region constants `se` / `OMXS30` / `SEK` (`defaults.py:3-5`).
- A standalone XSTO session-date builder with a three-tier source chain (`calendar.py:106-149`).
- A symbol-normalisation heuristic (`defaults.py:8-20`).

### Does **not** own

- **Market data.** No provider, no bundle, no ingestion. `qlib.init(provider_uri=...)` is entirely
  the consumer's responsibility, and `README.md:17` says so explicitly.
- **qlib's daily calendar.** This is the most commonly misread boundary in the repo.
  `build_xsto_trading_days` is **never called by `register()`** — grep confirms the only
  intra-package consumer of `calendar.py` is `region.py:9`, importing `se_trading_hours` alone
  ([E-11](evidence-log.md#e-11--internal-usage-of-de-facto-public-helpers)). qlib's trading-day
  calendar comes from the provider bundle's `calendars/day.txt`, not from this package. Roughly
  **150 of the package's 406 source lines sit outside the `register()` runtime path** and function
  as an offline bundle-generation utility. No document in the repo states this. (F-21)
- **Order routing, broker integration, backtest configuration, model training.** All in
  `qlib-trading`.
- **Credential provisioning.** `config.py` only *reads* `EODHD_API_KEY` or a user-scoped TOML.

## 5. Calendar source chain

`build_xsto_trading_days(start, end, use_cache=True)` (`calendar.py:106`) resolves in this order:

1. **Cache hit** — `_cache/xsto_<start>_<end>.csv`, exact `(start, end)` key match, no TTL, no
   source tag (`calendar.py:114-116`).
2. **EODHD** — only if an API key resolves. Fetches the `exchange-holidays/XSTO` endpoint and
   subtracts the returned dates from Mon–Fri business days (`calendar.py:90-103`). Result is
   discarded if empty (`calendar.py:122`).
3. **`pandas_market_calendars`** — `mcal.get_calendar("XSTO").schedule(...)` (`calendar.py:27-33`).
4. **Embedded CSV** — only reached if tier 3 raised (`calendar.py:137-149`).

Tiers 2 and 3 write their result to the cache; tier 4 does not. The cache does not record which
tier produced it, so a subsequent read cannot tell an EODHD-synthesised session set from a
PMC-authoritative one (F-16).

Tier ordering matters for correctness: tier 2 synthesises sessions from *business days minus
holidays*, which cannot express a half-day and cannot express an unscheduled closure, whereas
tier 3 carries the real XSTO schedule. The nominally *preferred* source is therefore the *least*
faithful one (F-06).

## 6. Ownership and bus factor

Full history is **6 commits, all dated 2025-10-24**
([E-10](evidence-log.md#e-10--repository-size-and-authorship)):

| Author | Commits |
|---|---:|
| Mattias Geisler `<mattias@geisler.se>` | 4 |
| maxilirator `<35955729+maxilirator@users.noreply.github.com>` | 2 |
| copilot-swe-agent[bot] | 1 |

The first two identities are the same person. Effective bus factor is **1**, with one
agent-authored commit. There is no `CODEOWNERS`, no review requirement visible in the workflow
config, and no `AGENTS.md` recording conventions for future agent contributors. The repository has
received no commits in the 9½ months between `55327d9` (2025-10-24) and this baseline (2026-08-09),
while remaining a hard runtime dependency of `qlib-trading`. (F-22)
