# 02 — Cross-repository interfaces and dependency direction

The consuming repository `qlib-trading` was available on disk as a checkout during this
assessment, so the statements below are read from its actual source rather than inferred
from this repository's documentation. Consumer paths are given relative to that checkout.

## 1. Dependency direction

```
        ┌──────────────────────┐
        │     qlib-trading     │   research + live handoff stack
        │  (package: q_train)  │
        └──────────┬───────────┘
                   │ depends on   "qlib-ext-se>=0.1.0"   (its pyproject.toml:14)
                   ▼
        ┌──────────────────────┐
        │     qlib_ext_se      │   this repository
        └──────────┬───────────┘
                   │ depends on   "pyqlib==0.9.7"        (pyproject.toml:20)
                   ▼
        ┌──────────────────────┐
        │        pyqlib        │   patched in place at runtime
        └──────────────────────┘
```

The direction is strictly one-way and acyclic: this repository contains **zero** references
to `qlib-trading` or `q_train` in code, tests, or packaging metadata. Its only mention of the
consumer is prose in `README.md:45` ("Using from a child app (e.g., qlib_trading)"). That is
the correct direction and should be preserved.

There is, however, a **diamond on pyqlib**, and the two branches disagree:

| Declarer | Constraint on pyqlib |
|---|---|
| `qlib_ext_se` (`pyproject.toml:20`) | `pyqlib==0.9.7` — exact |
| `qlib_ext_se` (`compat.py:7`, enforced at runtime) | `("0.9.7",)` — exact, raises otherwise |
| `qlib-trading` (`pyproject.toml:13`) | `pyqlib>=0.9` — open |

The consumer's constraint is strictly wider than what this package tolerates. Nothing
reconciles them at install time in the images that matter (contract C-5 below).

## 2. Declared vs. de-facto public API

**Declared** (`__init__.py:8`) — two names:

| Symbol | Signature | Consumer usage |
|---|---|---|
| `register()` | `() -> None` | 20+ call sites across the consumer's `scripts/` and `src/q_train/` |
| `unregister()` | `() -> None` | **zero** consumer call sites |

`register()` is the entire real interface. The consumer calls it in two styles — direct
`import qlib_ext_se; qlib_ext_se.register()` (e.g. `scripts/borsdata_sync.py:23,211`) and
defensive `importlib.import_module("qlib_ext_se")` (e.g. `scripts/walkforward_predict_and_merge.py:95`,
`scripts/stress_test_frozen_production.py:280`). Both reach the same function.

**De-facto public but unexported** — importable, documented in this repo's own README or
`INSTRUCTIONS.md`, and therefore part of the contract in practice:

| Symbol | Module | Documented at | Consumer usage |
|---|---|---|---|
| `build_xsto_trading_days(start, end, use_cache=True)` | `calendar` | — | none found |
| `is_trading_day(dt)` | `calendar` | — | none found |
| `se_trading_hours()` | `calendar` | `README.md:6,82` | none found |
| `get_eodhd_api_key()` | `config` | `README.md:21-27`, `INSTRUCTIONS.md:35-37` | none found |
| `normalize_symbol(symbol)` | `defaults` | `INSTRUCTIONS.md:21` | **none — consumer uses its own** |

Every one of these is reachable, none is in `__all__`, and none has a stability guarantee.
The gap between "documented as the hand-off contract" and "actually consumed" is the
recurring theme of this section.

## 3. Contracts

Each contract is stated as the consumer's expectation, then the verified status.

---

### C-1 — `register()` must precede `qlib.init(region="se")`

**Status: holds.** Enforced by discipline, not by code. The consumer follows it
consistently — `scripts/probe_qlib_features.py:88-92` even exposes a flag to *skip*
registration deliberately "to simulate vanilla qlib regions", and wraps the call in
`try/except` with `logging.exception`. If `register()` is skipped or fails, `qlib.init`
receives an unknown region.

Nothing in `qlib_ext_se` detects or reports out-of-order use.

---

### C-2 — `register()` is idempotent and safe to call from many entry points

**Status: holds, verified.** E-10. The consumer relies on this heavily: 20+ independent
scripts each call `register()` unconditionally at startup, and several import each other.

---

### C-3 — the region provides `deal_price="adjusted_close"` and `trade_unit=1`

**Status: holds, verified.** E-10 shows the exact dict installed into
`qlib.config._default_region_config["se"]`, matching the consumer-facing claim in
`README.md:83`.

---

### C-4 — the SE minute calendar reflects real Stockholm trading hours

**Status: does not hold for early-close days.** `se_trading_hours()` returns a constant
`("09:00:00", "17:30:00")` and the registered `get_min_cal` therefore always yields 510
one-minute bars. XSTO scheduled **4 early closes at 13:00 in 2025 alone** (2025-04-17,
2025-04-30, 2025-05-28, 2025-10-31), where the true bar count is 240 (E-09).

The consumer's manifests are daily-frequency, which is why this has not surfaced; it
becomes wrong the moment any minute-frequency path is used. See F-07.

---

### C-5 — the installed pyqlib is exactly 0.9.7

**Status: violated by the consumer on arm64.** The consumer's
`docker/Dockerfile.gpu.arm:57-60` states the problem in its own comment — "Work around
missing pyqlib==0.9.7 on arm64 by preinstalling a supported version, then install
qlib_ext_se without deps" — and then does exactly that:

```dockerfile
ARG QLIB_VERSION=0.9.3
RUN pip install --no-cache-dir pyqlib==${QLIB_VERSION} \
    && pip install --no-cache-dir --no-deps "git+https://github.com/maxilirator/qlib_ext_se.git@main#egg=qlib_ext_se"
```

`--no-deps` suppresses the exact-pin, so the image builds successfully. The conflict then
surfaces at runtime: `register()` raises
`RuntimeError: qlib-ext-se supports pyqlib versions ('0.9.7',), found 0.9.3` (E-13).

`docker/Dockerfile.gpu:68-78`, `Dockerfile.gpu.lite`, `Dockerfile.app-gpu-wheel` and
`Dockerfile.app-gpu-wheel-cupybase` share an arch-switch that defaults `aarch64|arm64` to
`0.9.3` and falls back to it if the requested version is unavailable — so the same
violation is reachable there. `Dockerfile.cpu:24` and
`Dockerfile.oracle-continuation-cloud:35` correctly pin `pyqlib==0.9.7`.

This is a **build-time-silent, runtime-fatal** mismatch. See F-04.

---

### C-6 — `qlib-ext-se>=0.1.0` is installable from the consumer's dependency list

**Status: holds only by accident.** The distribution name `qlib-ext-se` is **not published
on PyPI** — both `qlib-ext-se` and `qlib_ext_se` return HTTP 404 (E-14). The consumer's
GPU Dockerfiles install this package from git *first*, then run
`pip install $(… project.dependencies …)`, which includes `qlib-ext-se>=0.1.0`.

Verified pip behaviour (E-14): with 0.1.0 already installed, `pip install "qlib-ext-se>=0.1.0"`
reports *Requirement already satisfied* and never queries an index. The same command with
`>=0.2.0` fails hard:

```
ERROR: Could not find a version that satisfies the requirement qlib-ext-se>=0.2.0 (from versions: none)
```

So the consumer's build works today purely because the constraint floor equals the
currently installed version. **The first version bump of this package breaks the
consumer's image build** unless the constraint or the index is changed first. See F-08.

---

### C-7 — the embedded calendar fallback is available as a last resort

**Status: violated in every install the consumer actually performs.** The consumer's
Dockerfiles install via `pip install git+https://github.com/maxilirator/qlib_ext_se.git@main`,
which builds a wheel. The wheel contains six `.py` files and no data (E-06):

```
CSV present in wheel: False
```

`qlib_ext_se.data` has no `__init__.py`, so `[tool.setuptools.packages.find]` with
`include = ["qlib_ext_se*"]` does not discover it, and there is no `package-data`,
`include-package-data`, or `MANIFEST.in` to compensate.

Confirmed at runtime in a wheel-installed environment with tier 2 forced to fail (E-07):
the exception propagates rather than degrading to the embedded snapshot. Only the editable
install used by CI and by local development has the file. See F-02.

---

### C-8 — the extension supplies symbol normalization

**Status: not honoured on either side.** `INSTRUCTIONS.md:21` lists "symbol normalization
helper provided in this extension" as part of the hand-off. The consumer instead defines
`q_train.data.eodhd_utils.normalize_symbol`, plus `normalize_symbols` in
`q_train.data.access.instruments` and `normalize_symbol_from_record`. Their outputs are
mutually incompatible (E-16):

| Input | `qlib_ext_se` | `qlib-trading` |
|---|---|---|
| `'ERIC-B.ST'` | `'ERICB.ST'` | `'eric-b'` |
| `'VOLV-B'` | `'VOLVB.ST'` | `'volv-b'` |
| `'ABB.XSTO'` | `'ABB.XSTO.ST'` | `'abb'` |

They disagree on case, on suffix, and on hyphen handling — and the extension's version
mishandles the `.XSTO` suffix outright, producing a double-suffixed ticker. Because the
consumer never imports it, this is currently inert; it is a live trap for anyone who
follows `INSTRUCTIONS.md`. See F-10.

---

### C-9 — the git dependency resolves to a reviewed revision

**Status: does not hold.** All consumer Dockerfiles pin `@main`, a moving branch:

```dockerfile
RUN pip install --no-cache-dir "git+https://github.com/maxilirator/qlib_ext_se.git@main#egg=qlib_ext_se"
```

`docker/Dockerfile.gpu:61` carries the mitigating comment "For full reproducibility,
replace @main with a tag or commit SHA" — acknowledged and not done. Any commit to this
repository's default branch changes the next consumer image build, with no review gate
between the two repositories and no lock file on either side. See F-09.

## 4. Interface summary

| Contract | Subject | Status |
|---|---|---|
| C-1 | `register()` before `qlib.init` | holds (by convention) |
| C-2 | idempotent registration | holds — verified |
| C-3 | region defaults | holds — verified |
| C-4 | SE trading hours | **violated on early-close days** |
| C-5 | pyqlib exactly 0.9.7 | **violated on arm64 images** |
| C-6 | `qlib-ext-se>=0.1.0` installable | holds only until the next version bump |
| C-7 | embedded calendar fallback present | **violated in all wheel/git installs** |
| C-8 | extension supplies symbol normalization | not honoured; divergent duplicate |
| C-9 | pinned, reviewed dependency revision | **violated — `@main`** |
