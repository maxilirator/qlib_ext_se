# 02 — Cross-repository interfaces, version assumptions, and failure propagation

This document answers four questions about the boundary between `qlib-trading` (consumer)
and `qlib_ext_se` (this repository, provider):

1. **Which way does the dependency point?** — §1
2. **What are the integration contracts?** — §2, §3
3. **What version assumptions does each side make, and where are they enforced?** — §4
4. **When something breaks, how does the failure travel across the boundary — at which
   stage is it detected, what does the other side observe, and what is contained?** — §5

§6 summarises. §7 states which side owns each remediation, because several of the defects
found here are **not fixable in this repository**. §8 answers, item by item, the five
provider guarantees that the `qlib-trading` baseline explicitly delegates to this repository.

---

## 0. Provenance — how to re-verify every claim in this document

Consumer-side claims are read from an actual checkout, not inferred. Both sides are pinned
so that every citation below is re-derivable, and both pins are stated as **content
identity** rather than a bare commit SHA — documentation commits on either side move `HEAD`
without changing a line of the code these claims are about:

| Repository | Role | Pin used for every citation here |
|---|---|---|
| `maxilirator/qlib_ext_se` | provider (this repo) | `src` tree `6f1b143`, `tests` tree `d91f05a` — identical at `77d8754`, `049f406` (tip of `main`) and on this documentation branch |
| `maxilirator/qlib-trading` | consumer | `16425ce9f8fc85d717d9d84164418301e72dc69b` (`16425ce`), tip of `main` at 2026-08-09 21:19:58 +0200. Code trees identical to `c8e7c4b`, the round-1 pin: `git diff --name-only c8e7c4b 16425ce -- . ':!docs'` is empty |

Every `qlib-trading` path/line reference in this document is written as
`<path>:<line>` and resolves under **either** SHA. To reproduce any of them:

```console
$ git -C <qlib-trading> show 16425ce:<path> | sed -n '<line>p'
$ git -C <qlib-trading> grep -n "qlib_ext_se" 16425ce -- ':!docs' ':!profile.out'
```

Raw enumerations are in [`evidence-log.md`](evidence-log.md) as **E-19** (the complete
consumer coupling surface, enumerated at `c8e7c4b` and re-derived unchanged at `16425ce`)
and **E-20** (the containment experiment in §5.4). **E-22** records the round-2
re-derivation of both pins and of every measurement below.

This document adds no unverified claim about the consumer; where a statement depends on
running the consumer's images — which was not done — it is labelled **not executed** and
listed in §7 as belonging to operational verification.

---

## 1. Dependency direction

```
        ┌──────────────────────┐
        │     qlib-trading     │   research + live handoff stack
        │  (package: q_train)  │   main @ 16425ce
        └──────────┬───────────┘
                   │ depends on   "qlib-ext-se>=0.1.0"   (pyproject.toml:14)
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

**One-way and acyclic.** This repository contains **zero** references to `qlib-trading` or
`q_train` in code, tests, or packaging metadata. Its only mention of the consumer is prose
in `README.md:45` ("Using from a child app (e.g., qlib_trading)"). That is the correct
direction and should be preserved.

**There is a diamond on `pyqlib`, and the two branches disagree** — see §4.

**No repository-level reverse channel exists.** Nothing in `qlib_ext_se` calls back into,
imports from, subscribes to, or is notified by the consumer. The provider therefore cannot
observe consumer failures, and has no mechanism to warn the consumer of a breaking change.
Every cross-boundary effect in §5 therefore travels **downstream only** — and, as §5.3
shows, several of them travel without producing any signal at all.

---

## 2. The coupling surface — declared vs. de-facto public API

**Declared** (`__init__.py:8`, `__all__`) — two names:

| Symbol | Signature | Consumer usage at `16425ce` |
|---|---|---|
| `register()` | `() -> None` | **30 call sites across 28 Python files** (E-19) |
| `unregister()` | `() -> None` | **zero** call sites |

`register()` is the entire runtime interface. Verified exhaustively (E-19): across the
consumer's whole tree there is **no import of any `qlib_ext_se` submodule and no attribute
access other than `.register()`**. The consumer reaches it in two styles — direct
`import qlib_ext_se; qlib_ext_se.register()` (e.g. `src/q_train/workflow/launcher.py:39,41`;
`scripts/borsdata_sync.py:23,211`) and defensive
`importlib.import_module("qlib_ext_se")` (`scripts/walkforward_predict_and_merge.py:95-96`,
`scripts/stress_test_frozen_production.py:280-281`). Both reach the same function.

**De-facto public but unexported** — importable, documented in this repo's own `README.md`
or `INSTRUCTIONS.md`, and therefore part of the advertised hand-off contract:

| Symbol | Module | Documented at | Consumer usage |
|---|---|---|---|
| `build_xsto_trading_days(start, end, use_cache=True)` | `calendar` | — | none |
| `is_trading_day(dt)` | `calendar` | — | none |
| `se_trading_hours()` | `calendar` | `README.md:6,82` | none |
| `get_eodhd_api_key()` | `config` | `README.md:21-27`, `INSTRUCTIONS.md:35-37` | none |
| `normalize_symbol(symbol)` | `defaults` | `INSTRUCTIONS.md:21` | **none — consumer uses its own** |

Every one of these is reachable, none is in `__all__`, none has a stability guarantee, and
**none is consumed**. The gap between "documented as the hand-off contract" and "actually
consumed" is the recurring theme of this document — and, as §5.4 shows, it is also the
reason the highest-severity packaging defect (F-02) currently has no blast radius.

**Consequence for compatibility:** the real compatibility surface this repository must
preserve is one nullary function and the global state it installs into `pyqlib`. That is a
small, defensible contract. The documented-but-unused surface is a liability, not an asset.

---

## 3. Integration contracts

Each contract is stated as the consumer's expectation, then the verified status.

---

### C-1 — `register()` must precede `qlib.init(region="se")`

**Status: holds, by discipline only.** The consumer follows it consistently;
`scripts/probe_qlib_features.py:57-59,86-93` even exposes `--skip-extension` to *deliberately*
skip registration "to simulate vanilla qlib regions", and wraps the call in `try/except` with
`logging.exception(...)` followed by `raise`.

Nothing in `qlib_ext_se` detects or reports out-of-order use. If `register()` is skipped,
`qlib.init` receives an unknown region — see P-1 in §5.3 for what the consumer then sees.

---

### C-2 — `register()` is idempotent and safe to call from many entry points

**Status: holds, verified.** E-10. The consumer relies on this heavily: 28 independent
modules call `register()` unconditionally, several import each other, and
`src/q_train/data/qlib_data_connector.py:170-173` additionally guards with a process-global
`_GLOBAL_READY` flag. Two of the call sites are at **module import time**
(`src/q_train/workflow/launcher.py:41`, `src/q_train/stress/stress_test.py:22`), so
idempotency is load-bearing for the consumer's import graph, not merely for tidiness.

---

### C-3 — the region provides `deal_price="adjusted_close"` and `trade_unit=1`

**Status: holds, verified.** E-10 and E-20 both show the exact dict installed into
`qlib.config._default_region_config["se"]`:
`{'trade_unit': 1, 'limit_threshold': None, 'deal_price': 'adjusted_close'}` — matching the
consumer-facing claim in `README.md:83`.

---

### C-4 — the SE minute calendar reflects real Stockholm trading hours

**Status: does not hold for early-close days.** `se_trading_hours()` (`calendar.py:157-159`)
returns a constant `("09:00:00", "17:30:00")`, so the registered `get_min_cal` always yields
510 one-minute bars. XSTO scheduled **4 early closes at 13:00 in 2025 alone** (2025-04-17,
2025-04-30, 2025-05-28, 2025-10-31), where the true bar count is 240 (E-09).

**Propagation is silent** — the consumer's manifests are daily-frequency, so this produces
no error today. It becomes a wrong number, not an exception, the moment any minute-frequency
path is used. See F-07 and P-6 in §5.3.

---

### C-5 — the installed `pyqlib` is exactly 0.9.7

**Status: violated by the consumer on arm64, and violated by layer ordering on `Dockerfile.gpu`.**

`docker/Dockerfile.gpu.arm:57-60` states the problem in its own comment and then does it:

```dockerfile
# Work around missing pyqlib==0.9.7 on arm64 by preinstalling a supported version,
# then install qlib_ext_se without deps.
ARG QLIB_VERSION=0.9.3
RUN pip install --no-cache-dir pyqlib==${QLIB_VERSION} \
    && pip install --no-cache-dir --no-deps "git+https://github.com/maxilirator/qlib_ext_se.git@main#egg=qlib_ext_se"
```

`--no-deps` suppresses the exact pin, so the image builds. The conflict surfaces at runtime:
`RuntimeError: qlib-ext-se supports pyqlib versions ('0.9.7',), found 0.9.3` (E-13).

`docker/Dockerfile.gpu` has a subtler variant — **the pin is satisfied and then invalidated
by a later layer**:

| Line | Effect |
|---|---|
| `docker/Dockerfile.gpu:62` | installs `qlib_ext_se` **with** deps → pulls `pyqlib==0.9.7`, pin satisfied |
| `docker/Dockerfile.gpu:68-78` | arch switch: `x86_64→0.9.7`, `aarch64\|arm64→0.9.3`, `*→0.9.6`; **overwrites** the pyqlib installed above |
| `docker/Dockerfile.gpu:81` | reinstalls `qlib_ext_se` with `--no-deps` → pip never re-checks the pin |

On `x86_64` the arch default is `0.9.7` and the result is consistent. On `aarch64/arm64`, or
on any other arch (`*→0.9.6`), or with `--build-arg QLIB_VERSION=<anything else>`, the image
ends with a `pyqlib` this package rejects — and nothing in the build reports it.

The same `aarch64→0.9.3`, `*→0.9.6` switch appears in `docker/Dockerfile.gpu.lite:33-35`,
`docker/Dockerfile.app-gpu-wheel:51-53`, and `docker/Dockerfile.app-gpu-wheel-cupybase:34-36`.
`docker/Dockerfile.cpu:24` and `docker/Dockerfile.oracle-continuation-cloud:35` correctly pin
`pyqlib==0.9.7`.

**Build-time-silent, runtime-fatal.** See F-04 and P-2 in §5.3.

---

### C-6 — `qlib-ext-se>=0.1.0` is installable from the consumer's dependency list

**Status: holds only by accident, and one image has already had to work around it.**

The distribution name is **not published on PyPI** — both `qlib-ext-se` and `qlib_ext_se`
return HTTP 404 (E-14). The consumer's GPU Dockerfiles install this package from git *first*,
then run `pip install $(… project.dependencies …)`, which includes `qlib-ext-se>=0.1.0`.

Verified pip behaviour (E-14): with 0.1.0 already installed, `pip install "qlib-ext-se>=0.1.0"`
reports *Requirement already satisfied* and never queries an index. The same command with
`>=0.2.0` fails hard:

```
ERROR: Could not find a version that satisfies the requirement qlib-ext-se>=0.2.0 (from versions: none)
```

So the consumer's build works today purely because **the constraint floor equals the
currently installed version**. The first version bump of this package breaks the consumer's
image build unless the constraint or the index changes first.

Corroborating evidence that this is already felt on the consumer side:
`docker/build_runpod_runtime_requirements.py:9-18` generates the runpod image's requirements
from `pyproject.toml` while **explicitly stripping `qlib-ext-se`** from the list, and
`docker/Dockerfile.runpod-retune:62-64` then installs it separately as
`"qlib-ext-se @ git+https://github.com/maxilirator/qlib_ext_se.git@${QLIB_EXT_SE_REF}"`.
One image path has solved this; the others have not.

Two Dockerfiles additionally carry a PyPI fallback that cannot work:
`docker/Dockerfile.app-gpu-wheel:63` and `docker/Dockerfile.app-gpu-wheel-cupybase:45` use
`(pip install … git+… || pip install --no-cache-dir qlib-ext-se)`. Because the name is
unpublished, if the git install ever fails the fallback fails too — the `||` buys nothing but
a second, more confusing error. See F-08 and P-3 in §5.3.

---

### C-7 — the embedded calendar fallback is available as a last resort

**Status: violated in every install the consumer actually performs — but see §5.4, the
consequence is currently contained.**

The consumer installs via `pip install git+https://github.com/maxilirator/qlib_ext_se.git@…`,
which builds a wheel. The wheel contains six `.py` files and no data (E-06):

```
CSV present in wheel: False
```

`qlib_ext_se.data` has no `__init__.py`, so `[tool.setuptools.packages.find]` with
`include = ["qlib_ext_se*"]` does not discover it, and there is no `package-data`,
`include-package-data`, or `MANIFEST.in` to compensate. Confirmed at runtime in a
wheel-installed environment with tier 2 forced to fail (E-07): the exception propagates
rather than degrading to the embedded snapshot.

**Cross-boundary blast radius today: none.** E-20 proves `register()` never touches any
calendar data tier, and E-19 proves the consumer never imports the calendar module. This is
a latent defect at the boundary, not an active one — it activates the moment anyone follows
`README.md` and calls `build_xsto_trading_days` / `is_trading_day` from the consumer. See
F-02 and P-5 in §5.3.

---

### C-8 — the extension supplies symbol normalization

**Status: not honoured on either side.** `INSTRUCTIONS.md:21` lists "symbol normalization
helper provided in this extension" as part of the hand-off. The consumer instead defines
`q_train.data.eodhd_utils.normalize_symbol`, plus `normalize_symbols` in
`q_train.data.access.instruments` (used at `src/q_train/data/qlib_data_connector.py:217-218`)
and `normalize_symbol_from_record`. Their outputs are mutually incompatible (E-16):

| Input | `qlib_ext_se` | `qlib-trading` |
|---|---|---|
| `'ERIC-B.ST'` | `'ERICB.ST'` | `'eric-b'` |
| `'VOLV-B'` | `'VOLVB.ST'` | `'volv-b'` |
| `'ABB.XSTO'` | `'ABB.XSTO.ST'` | `'abb'` |

They disagree on case, on suffix, and on hyphen handling — and the extension's version
mishandles the `.XSTO` suffix outright, producing a double-suffixed ticker. Because the
consumer never imports it, this is currently inert; it is a live trap for anyone who follows
`INSTRUCTIONS.md`. See F-10 and P-7 in §5.3.

---

### C-9 — the git dependency resolves to a reviewed revision

**Status: does not hold.** Seven of the eight Dockerfiles that install this package resolve a
**moving branch** by default — four hardcode `@main`, three default an overridable
`QLIB_EXT_SE_REF` to it:

| Consumer file | Ref | Reviewed? |
|---|---|---|
| `docker/Dockerfile.gpu:62,81` | `@main` hardcoded | no |
| `docker/Dockerfile.gpu.arm:60` | `@main` hardcoded | no |
| `docker/Dockerfile.gpu.lite:42` | `@main` hardcoded | no |
| `docker/Dockerfile.oracle-continuation-cloud:36` | `@main` hardcoded | no |
| `docker/Dockerfile.app-gpu-wheel:60-63` | `ARG QLIB_EXT_SE_REF=main` | overridable, defaults unpinned |
| `docker/Dockerfile.app-gpu-wheel-cupybase:42-45` | `ARG QLIB_EXT_SE_REF=main` | overridable, defaults unpinned |
| `docker/Dockerfile.runpod-retune:62-64` | `ARG QLIB_EXT_SE_REF=main` | overridable, defaults unpinned |
| `docker/Dockerfile.cpu:41,46` | `ARG QLIB_EXT_SE_GIT` / editable install of `/app/ext/qlib_ext_se` if present | build-arg or vendored |

`docker/Dockerfile.gpu:61` carries the mitigating comment "For full reproducibility, replace
@main with a tag or commit SHA, e.g. @v0.1.0 or @<COMMIT_SHA>" — acknowledged and not done.
Neither repository has a lock file (verified: `qlib-trading` at `16425ce` tracks no
`requirements*.txt`, `*.lock`, or constraints file — E-19).

**Any commit to this repository's default branch changes the next consumer image build, with
no review gate between the two repositories.** This is the mechanism that turns every other
finding in this document into a cross-repository incident rather than a local one. See F-09
and §5.1.

A ninth consumption path exists and is not a `pip install` at all:
`docker/compose.ghcr.gpu.yaml:14` bind-mounts `../qlib_ext_se:/app/ext/qlib_ext_se` into the
container. That path carries the working tree, including `data/`, so C-7 holds there and C-9
is bypassed entirely — the running code is whatever is checked out on the host.

---

## 4. Version assumptions

Every version assumption at the boundary, who declares it, where it is enforced, and what
happens when it is violated. This consolidates statements previously scattered across C-5,
C-6, C-9 and [04](04-failure-modes.md).

| # | Assumption | Declared by | Enforced where | On violation |
|---|---|---|---|---|
| V-1 | `pyqlib == 0.9.7`, exactly | `qlib_ext_se/pyproject.toml:20` | pip, at install — **bypassed by `--no-deps`** in 3 consumer Dockerfiles | build succeeds, V-2 catches it later |
| V-2 | `pyqlib.__version__ in ("0.9.7",)` | `qlib_ext_se/compat.py:7` | runtime, first line of `register()` **and** of `unregister()` | `RuntimeError` at the consumer's first `register()` call (E-13) |
| V-3 | `pyqlib >= 0.9`, open | `qlib-trading/pyproject.toml:13` | pip, at install | never violated; strictly wider than V-1, so it silently admits versions V-2 rejects |
| V-4 | `qlib-ext-se >= 0.1.0` | `qlib-trading/pyproject.toml:14` | pip, at install | unsatisfiable from any index (E-14); holds only while the installed version is exactly the floor |
| V-5 | `requires-python >= 3.9`, no upper bound | `qlib_ext_se/pyproject.toml:10` | pip, at install | admits 3.13, where `pyqlib==0.9.7` has no wheel and no sdist; resolver error names **`pyqlib`, not this package** (E-04) → misdiagnosed as a test failure |
| V-6 | source revision = `@main` | 7 of 8 consumer Dockerfiles (4 hardcoded, 3 as an `ARG` default) | nothing | next build silently picks up any new commit (C-9) |
| V-7 | `tomllib` available (Python ≥ 3.11) for the TOML credential path | `qlib_ext_se/config.py:6-9` | guarded, returns `{}` when absent | on 3.9/3.10 — both inside V-5's declared range — a valid credential file is **silently ignored** (E-18) |

**The structural defect is V-1 vs. V-3.** The consumer declares a constraint strictly wider
than the one this package tolerates, and the strict side is enforced only at *runtime* (V-2).
Every "works on my machine, fails in the arm64 image" report at this boundary reduces to that
asymmetry. Two mutually exclusive fixes exist, and they belong to different repositories:

- **Provider-side (this repo):** widen V-1/V-2 to a tested range, or keep the pin and publish
  the package so V-4 can enforce it.
- **Consumer-side (`qlib-trading`):** tighten V-3 to `pyqlib==0.9.7` and stop using `--no-deps`,
  accepting that arm64 then has no supported build.

This repository can only do the first. See §7.

---

## 5. Failure propagation

### 5.1 Direction

Failures propagate **downstream only** (§1). There are exactly three channels by which a
defect in `qlib_ext_se` reaches `qlib-trading`:

1. **Install channel** — a `pip install git+…@main` in a consumer Dockerfile. Carries every
   change to this repository's default branch, unreviewed and unversioned (V-6).
2. **Import channel** — `import qlib_ext_se` in 29 consumer Python files. Carries import-time
   errors (missing module, missing transitive dependency).
3. **Call channel** — `qlib_ext_se.register()`, 30 call sites. Carries `RuntimeError` from the
   version gate (V-2), and — more dangerously — carries *silently wrong global state* into
   `pyqlib`, because `register()` mutates `qlib.config` and `qlib.utils.time` in place.

Channel 3 is the only one that can fail **without raising**. `register()` installs values
(C-3) and function replacements (C-4) that the consumer never validates; a wrong value there
becomes a wrong number in a backtest, not a stack trace.

### 5.2 Stages at which a cross-boundary failure can be detected

| Stage | What runs | Cost of a failure here |
|---|---|---|
| **S1 — image build** | consumer `docker build` | cheapest; CI catches it |
| **S2 — module import** | `import qlib_ext_se` at consumer module scope | container starts, then dies at first import |
| **S3 — `register()`** | version gate + monkey-patching | container starts, job dies at startup |
| **S4 — `qlib.init` / data access** | region lookup, calendar use | job dies mid-run, partial artifacts |
| **S5 — never** | wrong values used silently | **most expensive**: wrong research output, no signal |

### 5.3 Propagation table

Every finding at the boundary, traced from trigger to consumer-observed symptom.

| # | Trigger | Detected at | What `qlib-trading` observes | Contained? | Finding |
|---|---|---|---|---|---|
| **P-1** | `register()` skipped or not reached before `qlib.init` | S4 | `qlib.init(region="se")` with no `se` entry in `_default_region_config`; the consumer's only guard is `--skip-extension`, which is deliberate | no — this repo emits no out-of-order warning | C-1 |
| **P-2** | image installs `pyqlib != 0.9.7` (arm64 default, `*→0.9.6` default, or `QLIB_VERSION` override) | **S3, not S1** | `RuntimeError: qlib-ext-se supports pyqlib versions ('0.9.7',), found 0.9.3.` At `src/q_train/data/qlib_data_connector.py:178-185` this is caught and re-raised as `QlibDataError: Failed to initialize qlib: …`; at `src/q_train/workflow/launcher.py:41` and `src/q_train/stress/stress_test.py:22` it is an **uncaught import-time crash** | partially — fatal but loud, and the message names the fix | F-04 |
| **P-3** | this package's version is bumped above `0.1.0` | S1 | `ERROR: Could not find a version that satisfies the requirement qlib-ext-se>=0.2.0 (from versions: none)` in every image that installs deps from `pyproject.toml` | yes — build-time, loud | F-08 |
| **P-4** | any commit lands on this repo's `main` | **S5 until it breaks something** | nothing; next image build silently contains the new code | **no** — no gate, no lock, no changelog | F-09 |
| **P-5** | `pandas-market-calendars` unavailable/failing **and** a calendar API is called | S4 | in a wheel/git install the embedded tier does not exist, so the underlying exception propagates instead of degrading (E-07) | **yes, today** — by non-use, not by design (§5.4) | F-02 |
| **P-6** | any minute-frequency path on an XSTO early-close day | **S5** | 510 bars where 240 are real; no error, no warning | **no** — silently wrong | F-07 |
| **P-7** | anyone follows `INSTRUCTIONS.md:21` and adopts `qlib_ext_se.normalize_symbol` | **S5** | tickers normalized incompatibly with the consumer's own `normalize_symbols`; `.XSTO` inputs double-suffixed | yes, today — by non-use | F-10 |
| **P-8** | `qlib_ext_se` installed into a read-only `site-packages` and a calendar API is called | S4 | `PermissionError` writing `…/site-packages/qlib_ext_se/_cache/…` (E-11) | yes, today — by non-use | F-03 |
| **P-9** | consumer environment on Python 3.13 (admitted by V-5) | S1 | resolver error naming **`pyqlib`**, not this package (E-04) | partially — loud but misattributed | F-05 |
| **P-10** | `qlib_ext_se` missing or not importable | S2 | `src/q_train/data/qlib_data_connector.py:24-31` catches `ImportError` for `qlib`, `qlib.data.D` **and** `qlib_ext_se` in one `try`, sets `QLIB_AVAILABLE = False`, and later raises `QlibDataError("pyqlib is not installed. …")` — **the message names the wrong package** | no — misdiagnoses a provider-install failure as a `pyqlib` failure | new; see below |

**P-10 is a diagnosis defect at the boundary, and it is the consumer's to fix.** Because
`qlib` and `qlib_ext_se` share one import guard, a build in which the `git+…` install failed
(P-3's `||` fallback, a GitHub outage, a bad `QLIB_EXT_SE_REF`) surfaces to an operator as
"pyqlib is not installed" — pointing at the wrong repository. It is recorded here because
this document owns the boundary; the fix is in `qlib-trading`.

### 5.4 What is contained, and why (verified)

Three of the propagation paths above (P-5, P-7, P-8) do **not** currently reach the
consumer, despite the underlying defects being present in every consumer image. The reason is narrow and worth stating precisely, because it is easy to mistake
for a design property:

**They are contained by non-use, not by design.**

Two verified facts establish it:

1. **The consumer touches nothing but `register()`.** Exhaustive grep at `16425ce` (E-19):
   no `from qlib_ext_se import …`, no `qlib_ext_se.<submodule>` import, no attribute access
   other than `.register()`, in any of `src/`, `scripts/`, or `tests/`.
2. **`register()` never reaches a calendar data tier.** Verified by execution (E-20): with
   `build_xsto_trading_days`, `is_trading_day`, `_generate_with_pmc`, `_read_days_from_csv`,
   and `_fetch_holidays_eodhd` all replaced by raisers, **and** `socket.connect` disabled,
   `register()` still completes and installs the correct region config. The only calendar
   symbol on the `register()` path is `se_trading_hours()` (`region.py:9`, `calendar.py:157-159`),
   which returns a hardcoded tuple and performs no I/O.

So: the wheel's missing CSV (F-02), the cache-write `PermissionError` (F-03), and the
divergent `normalize_symbol` (F-10) are all real, all present in the images the consumer
builds, and all currently unreachable from the consumer. They activate on the first line of
consumer code that follows this repository's own `README.md`. **Reducing their priority on
the strength of this containment would be a mistake** — the containment is one import
statement deep.

The consumer does its own calendar work through `q_train.data.access.calendar.CalendarStore`
(`scripts/borsdata_sync.py:35,209`; note lines 207-212, which load that calendar *before*
calling `register()`), which is why it never needed this package's calendar.

### 5.5 What is not contained

- **P-2** (`pyqlib` mismatch) reaches the consumer on every non-x86_64 image build and is
  fatal at S3. Loud, but late.
- **P-4** (`@main`) has no containment whatsoever and is the amplifier for everything else:
  it is what makes a provider-side commit a consumer-side incident with no review step.
- **P-6** (early closes) has no containment and fails at S5 — silently wrong numbers.

### 5.6 Observability of a cross-boundary failure

There is **no cross-repository signal** other than the exception itself:

- `register()`'s only success signal is a `logger.info` at `region.py:89-97`, wrapped in a
  bare `except Exception: pass` (`region.py:98-99`) — so if the consumer's logging is not
  configured, or `qlib.log` raises, registration succeeds with **zero output**.
- The consumer has no post-registration assertion. `src/q_train/data/qlib_data_connector.py:190-199`
  (`_patch_registered_flag`) only `setdefault`s two boolean keys into `qlib.config.C._config`
  inside its own `try/except: pass`; it does **not** verify that `se` was registered or that
  the region defaults are the expected ones.
- Neither side records which version of this package a run used. Nothing writes
  `qlib_ext_se.__version__` (or the resolved git SHA) into a run manifest, MLflow tag, or log
  line, so a completed research artifact cannot be attributed to a provider revision.

**Consequence:** the failure modes that raise (P-2, P-3, P-9) are diagnosable from a stack
trace. The failure modes that do not raise (P-4, P-6) are, at present, **undetectable after
the fact**. That is the single most important operational statement in this document, and the
one cheapest to fix — see §7.

---

## 6. Interface summary

| Contract | Subject | Status | Propagates as |
|---|---|---|---|
| C-1 | `register()` before `qlib.init` | holds (by convention) | P-1, S4 |
| C-2 | idempotent registration | holds — verified | — |
| C-3 | region defaults | holds — verified | — |
| C-4 | SE trading hours | **violated on early-close days** | P-6, **S5 silent** |
| C-5 | `pyqlib` exactly 0.9.7 | **violated on arm64 and by `Dockerfile.gpu` layer order** | P-2, S3 |
| C-6 | `qlib-ext-se>=0.1.0` installable | holds only until the next version bump | P-3, S1 |
| C-7 | embedded calendar fallback present | **violated in all wheel/git installs** | P-5, contained today |
| C-8 | extension supplies symbol normalization | not honoured; divergent duplicate | P-7, contained today |
| C-9 | pinned, reviewed dependency revision | **violated — `@main` by default in 7 of 8 Dockerfiles** | P-4, **S5 silent** |

Version assumptions: V-1…V-7 in §4. Propagation paths: P-1…P-10 in §5.3.

---

## 7. Which repository owns each remediation

This document is the `qlib_ext_se` contribution to the cross-repository criterion. Several
defects at this boundary **cannot be fixed here**, and saying so precisely is part of the
deliverable.

### Owned by `qlib_ext_se` (this repository)

| Item | Remediation | Sequenced in |
|---|---|---|
| C-7 / P-5 | ship `data/xsto_trading_days_fallback.csv` in the wheel (package-data or `MANIFEST.in`) | [06](06-stabilization-sequence.md), F-02 |
| C-4 / P-6 | model XSTO early closes, or document the 510-bar grid as daily-only and fail loudly on minute use | F-07 |
| C-8 / P-7 | remove `normalize_symbol` from the advertised contract, or fix `.XSTO` and align it with the consumer | F-10 |
| V-1 / V-2 | decide the supported `pyqlib` range and make `pyproject.toml` and `compat.py` agree with it | F-04 |
| V-5 | add an upper bound to `requires-python` | F-05 |
| V-7 | depend on `tomli` below 3.11, or drop 3.9/3.10 from the declared range | F-17 |
| §5.6 | make registration observable: an unconditional log line carrying `__version__`, and a public predicate the consumer can assert on | F-19 |
| C-6 / V-4 | publish the distribution, or tag releases so the consumer can pin a ref | F-08 |
| C-9 / V-6 | tag releases; a moving `main` is only pinnable if there is something to pin to | F-09 |

### Owned by `qlib-trading` (consumer) — **not defects in this task**

| Item | Remediation |
|---|---|
| C-5 / P-2 | stop installing `pyqlib` *after* the extension in `docker/Dockerfile.gpu`; remove `--no-deps`; reconcile `pyqlib>=0.9` (V-3) with the provider's pin |
| C-9 / P-4 | replace `@main` with a tag or SHA in the 4 Dockerfiles that hardcode it; set a pinned default for `QLIB_EXT_SE_REF` in the other 3 |
| C-6 / P-3 | adopt the `Dockerfile.runpod-retune` pattern repo-wide (strip `qlib-ext-se` from generated requirements, install it explicitly), or pin the git ref |
| P-10 | split the `qlib` / `qlib_ext_se` import guard at `src/q_train/data/qlib_data_connector.py:24-31` so a missing extension is not reported as "pyqlib is not installed" |
| C-1 / P-1 | assert the region is registered after `register()` rather than relying on ordering |
| §5.6 | record `qlib_ext_se.__version__` (and the git SHA for `@main` installs) in run manifests / MLflow tags |
| C-6 | remove the `\|\| pip install qlib-ext-se` fallbacks, which cannot succeed against an unpublished name |

### Owned by final operational verification — **not establishable in either repository**

These require building and running the consumer's images, which this assessment did not do:

- Confirming that an arm64 `Dockerfile.gpu.arm` build actually reaches the P-2 `RuntimeError`
  in production (the mechanism is verified — E-12, E-13 — the end-to-end run is not).
- Confirming which images are currently deployed and on which architecture, and therefore
  how much of the fleet is affected by C-5.
- Confirming that no minute-frequency path is live anywhere, which is the premise of P-6's
  "no impact today".
- Determining which provider commit each historical research artifact was produced against —
  which, per §5.6, is **not currently recoverable** for any run already completed.

---

## 8. The five provider guarantees the consumer baseline delegates here

The `qlib-trading` baseline does not merely note that the provider is out of its scope — it
names the specific guarantees it needs and marks them **"Owned by `qlib_ext_se`; not
establishable in this checkout"** (`docs/production-readiness/qlib-trading-baseline.md:80`
and `docs/production-readiness/verification.md:26` at `16425ce`):

> the provider must declare its supported pyqlib/Python matrix, package-data/calendar
> guarantees, registration idempotency, and tested extension revision […] its supported
> compatibility matrix, registration idempotency, package data, reverse-import absence, and
> pinned revision must be established in the `qlib_ext_se` repository

Each is answered below with its evidence. Two are guarantees this repository can currently
give; two are **negative results** — the honest answer is that the guarantee does not hold
today; one is a fact rather than a promise.

### G-1 — Supported pyqlib / Python compatibility matrix

| Axis | Declared | Enforced | Actually exercised |
|---|---|---|---|
| `pyqlib` | `==0.9.7` (`pyproject.toml:20`) | `compat.py:7` at runtime, `SUPPORTED_PYQLIB_VERSIONS = ("0.9.7",)` | 0.9.7 only. 0.9.3 / 0.9.6 / 0.9.8 verified **rejected** with an actionable `RuntimeError` (E-13, E-22) |
| Python | `>=3.9`, no upper bound (`pyproject.toml:10`) | pip, at install | **3.12 only.** CI is single-version (`.github/workflows/ci.yml:14`); the `Dockerfile` uses `python:3.12-slim` |

**The declared matrix is wider than the tested one, in both axes and in opposite directions.**
`pyqlib` is declared narrower than it is proven to need (one version, exercised at that one
version — this is sound); Python is declared wider than anything tested, and wider than the
mandatory dependency supports: `pyqlib==0.9.7` publishes 18 wheels for cp38–cp312 and **no
sdist**, so 3.13 cannot resolve at all (E-04), and on 3.9/3.10 the TOML credential path is
silently inert because `tomllib` is 3.11+ (E-18).

**Guarantee this repository can give today:** pyqlib exactly 0.9.7 on CPython 3.12.
Everything else in the declared range is untested. F-05 and F-17 track the correction; V-1,
V-2, V-5 and V-7 in §4 state where each is enforced.

### G-2 — Registration idempotency

**Holds — verified by execution, not by inspection (E-10, re-run in E-22).**

- `register()` is guarded per patch: constants (`region.py:17`), region config
  (`region.py:26`), and the `_ORIGINALS` capture (`region.py:47-50`) each write only when
  absent. A second call does not grow `_default_region_config`.
- The installed region config is exactly
  `{'trade_unit': 1, 'limit_threshold': None, 'deal_price': 'adjusted_close'}` (C-3).
- Non-`se` regions are untouched: `cn` still yields 240 minute bars after registration.
- `unregister()` restores `get_min_cal` to the **identical original function object**, and
  removes `REG_SE`.
- `register()` completes with every calendar tier sabotaged and outbound sockets disabled
  (E-20), so it is idempotent *and* I/O-free — which is why the consumer's two import-time
  call sites are safe.

This is the guarantee the consumer relies on most heavily (28 modules, 2 of them at import
time) and it is the one in the best shape. One asymmetry is recorded as F-16: `unregister()`
removes state regardless of who installed it.

### G-3 — Package-data and calendar guarantees

**Does not hold as packaged. This is F-02, the P0 of this baseline.**

| Question | Answer | Evidence |
|---|---|---|
| Is the fallback calendar shipped in a wheel? | **No.** The wheel contains 6 `.py` files and `dist-info`, nothing else | E-06, E-22 |
| Is it present in the install method the consumer uses (`pip install git+…`)? | **No** — that path builds the same wheel | E-06/E-07 |
| Does the documented three-tier degradation work there? | **No** — with tier 2 forced to fail the exception propagates | E-07 |
| Is the calendar data itself correct where it *is* present? | **Yes, exactly** — 9,041 sessions, 2000-01-03 → 2035-12-28, zero divergence from `pandas-market-calendars` XSTO in either direction | E-08, E-22 |
| Are the calendar tiers equivalent? | **No** — tier 1 synthesizes Mon–Fri minus an EODHD holiday list; an empty holiday response yields 261 sessions for 2025 against the exchange's 249 | E-23, F-13 |
| Are session *hours* modelled per date? | **No** — a constant 09:00–17:30, so 510 minute bars on the 4 XSTO early-close days of 2025 where 240 are real | E-09/E-10, F-07 |

**Guarantee this repository can give today:** in an **editable/source** install the embedded
calendar is present and exactly correct. In a **wheel or git** install — every consumer image
— it is absent. Remediation is Step 2 of [06](06-stabilization-sequence.md); the deliverable
is the packaging test, not the one-line config change.

### G-4 — Reverse-import absence

**Holds — verified exhaustively (E-24).** `grep -rniE "q_train|qlib[-_]trading"` over `src/`,
`tests/`, `pyproject.toml`, `Dockerfile` and `.github/` returns **no match**. The single
occurrence anywhere in the tracked tree is prose in `README.md:45` ("Using from a child app
(e.g., qlib_trading)"). There is no import, no optional import, no entry point, no
`extras_require`, and no test fixture referencing the consumer.

The dependency graph is therefore one-way and acyclic, as §1 states and as the consumer's own
baseline requires ("the extension must not import `q_train`"). This is the one delegated
guarantee that is unconditionally satisfied.

### G-5 — Tested revision identity, and what can be pinned

**A fact, not yet a guarantee.** There is nothing to pin *to*: no tag, no release, no
published distribution (`qlib-ext-se` and `qlib_ext_se` both 404 on PyPI — E-14), and no lock
file on either side (E-19). Seven of the eight consumer Dockerfiles resolve `@main` (C-9).

What this baseline can offer instead is **content identity**: all evidence here was produced
against `src` tree `6f1b143` and `tests` tree `d91f05a`, which are identical at `77d8754`,
at `049f406` (tip of `main`), and on this documentation branch (E-22). A release pin can be
cut from any commit carrying those trees and this document set still describes it exactly.

**What the consumer should pin, once Step 1 of [06](06-stabilization-sequence.md) lands:** a
tag on a commit whose `src` tree is `6f1b143` — noting that such a tag would ship the F-02
packaging defect, so Step 2 should precede the first tag the consumer actually adopts.

### Guarantee summary

| # | Guarantee requested by `qlib-trading` | Status here | Tracked as |
|---|---|---|---|
| G-1 | Supported pyqlib/Python matrix | **Partial** — pyqlib 0.9.7 + CPython 3.12 only; declared Python range is untested and partly unsatisfiable | F-05, F-17, V-1/V-5/V-7 |
| G-2 | Registration idempotency | **Holds, verified** | C-2, E-10, E-20 |
| G-3 | Package-data / calendar guarantees | **Does not hold in wheel/git installs**; the data itself is exact where present | F-02, F-07, F-13 |
| G-4 | Reverse-import absence | **Holds, verified exhaustively** | §1, E-24 |
| G-5 | Tested/pinned revision | **No pinnable artifact exists**; content identity supplied instead | F-08, F-09 |

G-1, G-3 and G-5 are provider-side work, sequenced in [06](06-stabilization-sequence.md).
None of the three can be closed by the consumer, and none is a defect of the consumer's
baseline for having been delegated.
