# 01 — Architecture and ownership boundaries

Assessed against `src` tree `6f1b143` / `tests` tree `d91f05a` — identical at `77d8754`, at
`049f406` (tip of `main`), and on this documentation branch (E-22). Line references below are
to the working tree at those trees.

## 1. What this package is

`qlib_ext_se` adds a Sweden region (`se`) to `pyqlib` 0.9.7 **by mutating pyqlib's module
namespace at runtime**. It is not a plugin in any framework-supported sense; pyqlib 0.9.7
has no region-extension entry point, so the package reaches into three pyqlib modules and
patches them in place.

This is the single most important architectural fact about the repository, and it
determines nearly everything in [04 — Failure modes](04-failure-modes.md): the package's
correctness is coupled to pyqlib's *internal* layout, not to a public API, which is why
the version gate is pinned to one exact version.

## 2. Module map

The whole package is 229 executable statements across 6 modules.

| Module | Stmts | Responsibility | Depends on |
|---|---|---|---|
| `__init__.py` | 3 | Public API re-export; `__version__ = "0.1.0"` | `region` |
| `region.py` | 83 | All pyqlib monkey-patching; `register()` / `unregister()` | `compat`, `defaults`, `calendar`, pyqlib, pandas |
| `calendar.py` | 92 | XSTO session sourcing, 3-tier fallback, CSV cache | `config`, pandas, `pandas_market_calendars`, `requests` |
| `config.py` | 29 | EODHD API-key lookup (env → user TOML) | `tomllib` (3.11+) |
| `compat.py` | 10 | pyqlib version gate | pyqlib |
| `defaults.py` | 12 | `REGION_CODE` / `INDEX` / `CURRENCY`, `normalize_symbol` | — |

Data: `data/xsto_trading_days_fallback.csv`, 9,041 sessions, 2000-01-03 → 2035-12-28.

Dependency direction inside the package is acyclic and shallow:

```
__init__ ──▶ region ──┬──▶ compat            (version gate, called first)
                      ├──▶ defaults          (constants)
                      └──▶ calendar ──▶ config
```

`calendar.py` is the only module with outbound network capability. `region.py` is the only
module that mutates global state.

## 3. The `register()` runtime path

`register()` (`region.py:102-111`) makes five calls, in order — a version gate, three
mutations, and a log line — with no transaction semantics: a failure in step 4 leaves steps
2–3 applied.

| Step | Function | Mutation | Reversible? |
|---|---|---|---|
| 1 | `ensure_pyqlib_supported()` | none (raises if pyqlib ≠ 0.9.7) | n/a |
| 2 | `_monkey_patch_constants()` | sets `qlib.constant.REG_SE = "se"` | yes, `unregister` deletes it |
| 3 | `_patch_default_region_config()` | inserts `qlib.config._default_region_config["se"]` | yes, `unregister` pops it |
| 4 | `_patch_time_utils()` | replaces `qlib.utils.time.get_min_cal` and `.time_to_day_index` | yes, originals cached in `_ORIGINALS` |
| 5 | `_structured_info_log()` | log line only; all exceptions swallowed | n/a |

Verified behaviour (E-10):

- The region config installed is `{'trade_unit': 1, 'limit_threshold': None, 'deal_price': 'adjusted_close'}`.
- `register()` is idempotent — each patch is guarded by an existence check, and a second
  call does not grow `_default_region_config`.
- The `se` minute calendar is 510 entries, `09:00:00` → `17:29:00`.
- The `cn` minute calendar is unchanged at 240 entries: the patch delegates to the stored
  original for every non-`se` region, so **other regions are not affected**.
- `unregister()` restores `get_min_cal` to the identical original object and removes `REG_SE`.

The rollback path is genuinely correct, which is unusual for monkey-patching code and
worth preserving. Its one flaw is that it is unconditional rather than ownership-aware
(F-16).

`_ORIGINALS` is module-global and populated only once (`region.py:47-50`), so
register→unregister→register cycles restore the true originals rather than accumulating
wrappers.

## 4. The calendar tier system

`build_xsto_trading_days(start, end, use_cache=True)` (`calendar.py:106-149`) resolves
sessions through four tiers, first success wins:

| Tier | Source | Trigger | Session basis |
|---|---|---|---|
| 0 | CSV cache under `<package>/_cache/` | `use_cache` and file exists | whatever produced it |
| 1 | EODHD holidays endpoint | an API key is resolvable | **synthesized**: Mon–Fri minus holidays |
| 2 | `pandas-market-calendars` XSTO | tier 1 absent or empty | exchange schedule |
| 3 | embedded `xsto_trading_days_fallback.csv` | tier 2 raises | frozen snapshot |

Two structural observations:

- **Tiers 1 and 2 do not produce the same kind of answer.** Tier 1 synthesizes sessions
  from weekday arithmetic minus a holiday list; tier 2 reads a maintained exchange
  schedule. They can disagree, the result is cached without recording which tier produced
  it, and nothing reconciles them (F-13).
- **The tier ordering makes the highest-risk source the default.** Tier 1 is preferred
  whenever a key is present, so the presence of an environment variable silently changes
  the calendar's provenance.

The cache is keyed on the `(start, end)` pair, so `is_trading_day(d)` — which calls
`build_xsto_trading_days(d, d)` — creates one CSV file per distinct date queried (F-12,
observed in E-11: four files after a 4-date test run).

## 5. Ownership boundaries

| Concern | Owner | Boundary evidence |
|---|---|---|
| pyqlib region registration | `qlib_ext_se` | sole implementation; no equivalent in consumer |
| Stockholm session calendar | `qlib_ext_se` | `calendar.py` + embedded CSV |
| SE trading hours | `qlib_ext_se` | `se_trading_hours()`, hardcoded |
| SE region defaults (`trade_unit`, `deal_price`) | `qlib_ext_se` | `region.py:27-31` |
| EODHD **calendar/holiday** access | `qlib_ext_se` | `calendar.py:46-87` |
| EODHD **price/market data** access | `qlib-trading` | consumer's `scripts/eodhd_sync.py` |
| Symbol normalization | **contested** | two divergent implementations, see F-10 and [02](02-cross-repository-interfaces.md) |
| Qlib data bundle on disk | `qlib-trading` | consumer owns `provider_uri` and the `data/xsto` layout |
| Model training, backtest, live handoff | `qlib-trading` | no such code here |

The boundary is clean except for two leaks:

**Symbol normalization is owned by neither and implemented by both.**
`qlib_ext_se.defaults.normalize_symbol` exists and `INSTRUCTIONS.md:21` advertises it as
part of the hand-off contract, but the consumer does not import it — it uses its own
`q_train.data.eodhd_utils.normalize_symbol`, whose output is incompatible in every
non-trivial case (E-16). The extension's copy is unreferenced code presented as an
interface.

**EODHD credential handling is split.** Both repositories read EODHD credentials
independently, with different resolution rules, and this repository additionally carries a
committed token in `pyproject.toml` that nothing reads (F-01). There is no single owner of
the credential lifecycle.

## 6. What is *not* in this repository

Recorded so the boundary is unambiguous: no data ingestion, no model code, no backtest, no
scheduler, no service, no deployment manifest, no persistent state. The `Dockerfile` builds
a test-runner image only, and the consumer's own documentation notes the extension does not
require its own container (`README.md:85`). This package is a library, and treating it as
one is correct.
