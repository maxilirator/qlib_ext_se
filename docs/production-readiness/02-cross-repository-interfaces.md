# 02 — Cross-repository interfaces and dependency direction

Baseline commit `77d8754`.

## 1. Dependency direction

```
        qlib-trading  (consumer, separate repository)
              │  imports qlib_ext_se; calls register() before qlib.init
              ▼
        qlib_ext_se   (THIS repository)
              │  hard pin: pyqlib == 0.9.7
              ▼
        pyqlib 0.9.7  (upstream, third party)
```

The direction is **strictly one-way and acyclic**. Nothing in this repository imports, references,
or names `qlib-trading` in code. `README.md:45-85` documents the consumer integration, and
`pyproject.toml:29` points `Homepage` at this repository's own GitHub URL; there is no build-time,
test-time, or runtime coupling back toward the consumer.

This is the correct direction and should be preserved. The two concrete risks to it are that the
consumer currently depends on **unexported** symbols (§3) and on **undeclared data-shape
requirements** (§4).

### Distribution channel

`README.md:47-53` offers two options: `pip install -e .` from a checkout, or publishing to an
artifact registry as `qlib-ext-se`. There is no published release, no release workflow, and no tag
in this repository — so in practice the consumer resolves the dependency by path or VCS reference.
This matters because the editable path and the wheel path **do not ship the same files** (F-02, see
[E-05](evidence-log.md#e-05--wheel-contents)): the editable install has the embedded fallback
calendar and a built wheel does not.

## 2. Declared public API

`__init__.py:8` exports exactly two names:

| Symbol | Signature | Contract |
|---|---|---|
| `register()` | `() -> None` | Idempotent. Raises `RuntimeError` if pyqlib is missing or its version is not exactly `0.9.7` (`compat.py:23-27`). **Must be called before `qlib.init(region='se')`.** |
| `unregister()` | `() -> None` | Documented as "best-effort rollback" (`region.py:115`). Actually raises `RuntimeError` when pyqlib is absent (`region.py:116`). |

`__version__ = "0.1.0"` (`__init__.py:10`) is hand-synchronised with `pyproject.toml:7`; nothing
enforces agreement.

## 3. De-facto public surface (unexported but reachable)

These are not in `__all__` but are importable, documented in prose, or named in the hand-off
checklist. They form an **undeclared interface** — changing them is a breaking change for the
consumer with no signal from `__all__` or the version number.

| Symbol | Location | Status in this repo | Notes |
|---|---|---|---|
| `calendar.build_xsto_trading_days(start, end, use_cache=True)` | `calendar.py:106` | Used only by `is_trading_day` and one test | The offline bundle-generation entry point |
| `calendar.is_trading_day(date)` | `calendar.py:152` | Used only by `tests/test_calendar_dates.py` | Writes a cache file **per date queried** (F-07) |
| `calendar.se_trading_hours()` | `calendar.py:157` | Consumed by `region.py:39` | Returns `("09:00:00", "17:30:00")`; no half-day variant (F-06) |
| `config.get_eodhd_api_key()` | `config.py:31` | Consumed by `calendar.py:119` | Env `EODHD_API_KEY` → user TOML. **Never reads `pyproject.toml`** |
| `defaults.normalize_symbol(symbol)` | `defaults.py:8` | **Zero call sites anywhere in the repo**, including tests | Advertised in `INSTRUCTIONS.md:21` as a delivered registry item (F-18) |
| `defaults.REGION_CODE / INDEX / CURRENCY` | `defaults.py:3-5` | `"se"` / `"OMXS30"` / `"SEK"` | |

Verified by grep across the tree —
[E-11](evidence-log.md#e-11--internal-usage-of-de-facto-public-helpers).

`normalize_symbol` is additionally **lossy for Swedish share classes**
([E-12](evidence-log.md#e-12--normalize_symbol-behaviour)):

| Input | Output | Correct Nasdaq Stockholm / EODHD ticker |
|---|---|---|
| `ERIC-B` | `ERICB.ST` | `ERIC-B.ST` |
| `VOLV-B.ST` | `VOLVB.ST` | `VOLV-B.ST` |
| `ATCO-A` | `ATCOA.ST` | `ATCO-A.ST` |

`defaults.py:19` strips hyphens unconditionally. Any consumer that routes instrument identifiers
through this helper will produce identifiers that do not resolve against EODHD or a bundle keyed on
the exchange convention. It is unused here, which is what makes it dangerous — it looks available
and endorsed.

## 4. Contract imposed on the pyqlib side

Verified against the actual `pyqlib-0.9.7-cp312-...-manylinux_2_17_x86_64.whl`
([E-07](evidence-log.md#e-07--pyqlib-097-region-config-and-patch-target-analysis)).

### 4.1 Region config shape — satisfied

pyqlib 0.9.7 `qlib/config.py` defines `_default_region_config` with `REG_CN` / `REG_US` / `REG_TW`,
each carrying exactly `trade_unit`, `limit_threshold`, `deal_price`. The injected `"se"` entry
(`region.py:27-31`) matches that shape. `QlibConfig.set_region` does
`self.update(_default_region_config[region])` — an unguarded dict index, which is precisely why the
call ordering in §2 is load-bearing.

### 4.2 `deal_price = "adjusted_close"` — an undeclared **data** contract

`qlib/backtest/exchange.py` normalises the configured `deal_price` by prefixing `$` when absent, so
this setting resolves to the expression field **`$adjusted_close`** in whatever provider bundle the
consumer supplies. If that field is missing, `NaN`, or `<= 1e-08`, the exchange logs a warning and
**silently substitutes the close price** rather than failing.

This is the single most consequential cross-repository requirement in the package, and it is stated
nowhere in `README.md`, `INSTRUCTIONS.md`, or any test:

> **The SE provider bundle owned by `qlib-trading` must expose an `$adjusted_close` field for every
> instrument and session used in backtest, or every fill silently reverts to close price.**

Tracked as F-11. `tests/test_dataset_smoke.py` exercises `DatasetH` but never touches the exchange
or `deal_price`, so no test would catch this.

### 4.3 Monkey-patch reach — partially satisfied

- `qlib/utils/time.py` calls `get_min_cal(...)` through the **module global** (twice), so the patch
  reaches those callers.
- `qlib/contrib/ops/high_freq.py` does `from qlib.utils.time import time_to_day_index` at module
  scope. If that module is imported before `register()` runs, the name stays bound to the original
  function and the patch has no effect there. That module also calls it **without a `region`
  argument**, so it defaults to `REG_CN` and applies the Chinese session mapping regardless of
  patch order. High-frequency SE ops are therefore not covered by this extension at all. (F-09)

### 4.4 Version gate — brittle by design

`compat.py:7` pins `SUPPORTED_PYQLIB_VERSIONS = ("0.9.7",)` and `compat.py:23` performs exact
string membership. Any pyqlib upgrade, including a patch release, hard-fails `register()`. That is
a defensible choice for a monkey-patching shim, but it means the consumer's pyqlib version is
effectively frozen by this dependency.

## 5. Contract imposed on the `qlib-trading` side

The following are **cited from the initiative's `qlib-trading` inventory** and were **not
re-verified in this checkout** — this repository has no visibility into the consumer:

- `src/q_train/workflow/launcher.py` registers `qlib_ext_se` and then initialises qlib.
- `src/q_train/data/qlib_data_connector.py` validates the Stockholm data bundle.
- The canonical short manifest `workflows/canonical/short_live/v1/stack_short_trial36_v1.yaml`
  records `lan_shadow_pipeline_complete: false` and `live_broker_commit_enabled: false`.

Combining that with what **is** verifiable here, the consumer must satisfy all of:

| # | Requirement | Source of truth | Enforced anywhere? |
|---|---|---|---|
| C-1 | Call `qlib_ext_se.register()` **before** `qlib.init(region='se')` | `qlib/config.py` `set_region` | No — prose only |
| C-2 | Pin `pyqlib==0.9.7` exactly | `compat.py:7` | Yes — `RuntimeError` at `register()` |
| C-3 | Run on CPython 3.9–3.12 | pyqlib wheel availability ([E-02](evidence-log.md#e-02--pyqlib-097-distribution-availability)) | No — `requires-python` says `>=3.9`, unbounded (F-04) |
| C-4 | Provide `$adjusted_close` in the bundle | `qlib/backtest/exchange.py` | No — silent degradation |
| C-5 | Provide `calendars/day.txt` for SE sessions | qlib provider layer | No — outside this package (§ 01-4) |
| C-6 | Supply `EODHD_API_KEY` via env or user TOML if the EODHD calendar tier is wanted | `config.py:38-47` | No — absent key silently downgrades to PMC |
| C-7 | Ensure the runtime user can write inside the installed package directory, **or** accept that the calendar cache fails | `calendar.py:13,20` | No — `os.makedirs` will raise on a read-only filesystem (F-07) |
| C-8 | Install editable, or vendor the fallback CSV separately | wheel contents ([E-05](evidence-log.md#e-05--wheel-contents)) | No (F-02) |

C-1, C-4, C-7 and C-8 are the four that can fail *in production, silently or late*. They are the
interface hardening priorities in [`06-stabilization-sequence.md`](06-stabilization-sequence.md).

## 6. Interface stability assessment

| Dimension | State |
|---|---|
| Declared API breadth | Minimal and appropriate (2 symbols) |
| Declared vs actual surface | **Mismatched** — six unexported symbols are reachable and one is advertised in `INSTRUCTIONS.md` |
| Versioning | `0.1.0`, no tags, no CHANGELOG, no release process — the consumer has no way to pin a reviewed revision other than a commit SHA |
| Typing | No `py.typed`; annotations exist but are invisible to consumers under PEP 561 |
| Breaking-change signal | None |
