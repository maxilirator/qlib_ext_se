# Production-readiness baseline — `qlib_ext_se`

Baseline date: **2026-08-09**
Commit under review: **`77d8754`** (`agent/task-49eeb3b6-5110edba`, identical tree to `origin/main`)
Repository: `https://github.com/maxilirator/qlib_ext_se`
Scope: this repository, plus the interface it exposes to its single known consumer, `qlib-trading`.

This baseline is **documentation only**. No runtime code, configuration, dependency, credential,
deployment state, or external service was modified while producing it. Every claim below is
traceable to a `file:line` reference in this checkout or to a command recorded in
[`evidence-log.md`](evidence-log.md).

## Documents

| # | Document | Covers |
|---|---|---|
| — | [`evidence-log.md`](evidence-log.md) | Every command run, its output, and the environment it ran in |
| 01 | [`01-architecture-and-ownership.md`](01-architecture-and-ownership.md) | Module map, runtime path, what the package does and does not own |
| 02 | [`02-cross-repository-interfaces.md`](02-cross-repository-interfaces.md) | Dependency direction, the `qlib-trading` contract, the pyqlib contract |
| 03 | [`03-setup-test-run.md`](03-setup-test-run.md) | Reproducible install, test, and container procedures with observed results |
| 04 | [`04-failure-modes.md`](04-failure-modes.md) | 22 prioritized failure modes, P0→P3, each with evidence and blast radius |
| 05 | [`05-operational-gaps.md`](05-operational-gaps.md) | Release, observability, ownership, and supply-chain gaps |
| 06 | [`06-stabilization-sequence.md`](06-stabilization-sequence.md) | Ordered remediation sequence with exit criteria |

## Executive assessment

`qlib_ext_se` is a **486-line, six-module runtime shim** that teaches pyqlib 0.9.7 about a Swedish
(`se`) region by monkey-patching three points in the qlib process namespace. It is small, it is
readable, and its core calendar data is demonstrably correct. It is **not production-ready as
packaged**, for reasons that are mostly packaging, supply-chain, and operational rather than
algorithmic.

**What is verified sound:**

- The embedded fallback calendar is exact. All 9,041 sessions in
  `src/qlib_ext_se/data/xsto_trading_days_fallback.csv` for 2000-01-03 … 2035-12-28 match
  `pandas_market_calendars` XSTO with **zero divergence in either direction**
  ([evidence E-04](evidence-log.md#e-04--embedded-calendar-vs-pandas-market-calendars-xsto)).
  No weekend sessions; per-year session counts 249–254 are plausible throughout.
- Hardcoded trading hours `09:00:00`–`17:30:00` (`src/qlib_ext_se/calendar.py:157`) match the XSTO
  regular session in `Europe/Stockholm` exactly ([E-06](evidence-log.md#e-06--xsto-regular-and-early-close-sessions)).
- The injected region dict (`src/qlib_ext_se/region.py:27`) has exactly the key shape pyqlib 0.9.7
  expects — `trade_unit`, `limit_threshold`, `deal_price` — matching `REG_CN`/`REG_US`/`REG_TW`
  ([E-07](evidence-log.md#e-07--pyqlib-097-region-config-and-patch-target-analysis)).
- `register()` is genuinely idempotent: originals are captured once behind a guard
  (`src/qlib_ext_se/region.py:47-50`) and each wrapper delegates to the stored original, so
  repeat calls cannot stack wrappers.
- The internal callers inside `qlib/utils/time.py` resolve `get_min_cal` through the module global,
  so the patch does take effect on the primary code path.

**What blocks production use:**

| ID | Blocker | Evidence |
|---|---|---|
| **F-01** | A live EODHD API token is committed at `pyproject.toml:43-44` and has been in the public git history since `55327d9` (2025-10-24). It is also *inert* — nothing in the package reads `pyproject.toml`. | [E-08](evidence-log.md#e-08--committed-credential-in-git-history) |
| **F-02** | The built wheel **omits** `qlib_ext_se/data/xsto_trading_days_fallback.csv`. Any non-editable install loses the last-resort calendar tier entirely. | [E-05](evidence-log.md#e-05--wheel-contents) |
| **F-03** | `pytest -q` reports **2 failed, 2 passed, 1 skipped** without pyqlib present; the registration tests hard-fail instead of skipping. | [E-03](evidence-log.md#e-03--test-suite-execution) |
| **F-04** | `requires-python = ">=3.9"` is unbounded, but pyqlib 0.9.7 ships **cp38–cp312 wheels and no sdist**. Install is impossible on Python 3.13+. | [E-02](evidence-log.md#e-02--pyqlib-097-distribution-availability) |
| **F-05** | The Dockerfile's documented "smoke test" runs **zero tests** — `tests/` is never copied into the image; `pytest` exits 5. | [E-09](evidence-log.md#e-09--pytest-exit-code-with-no-tests-collected) |

Full ranked list, including the half-day-session gap (F-06), the cache-writes-into-site-packages
defect (F-07), and the undeclared `$adjusted_close` data contract (F-11), is in
[`04-failure-modes.md`](04-failure-modes.md).

## Verification status of the initiative criteria

| Required criterion | Status | Where |
|---|---|---|
| Architecture and ownership boundaries | Verified from repository evidence | [01](01-architecture-and-ownership.md) |
| Cross-repository interfaces and dependency direction | Verified for this side of the boundary; the `qlib-trading` side is cited from the initiative inventory and explicitly marked as not re-verified here | [02](02-cross-repository-interfaces.md) |
| Reproducible setup / test / run procedures | Executed; observed results recorded, including the two that fail | [03](03-setup-test-run.md), [E-01…E-03](evidence-log.md) |
| Prioritized failure modes | 22 findings, ranked P0–P3, each with a concrete failure scenario | [04](04-failure-modes.md) |
| Operational gaps | Verified | [05](05-operational-gaps.md) |
| Stabilization sequence | Ordered, with exit criteria per step | [06](06-stabilization-sequence.md) |

## Scope note on the approved plan

The initiative objective states that no file outside `docs/production-readiness/` may be modified.
The pre-approval plan record carries `changed_files: ["pyproject.toml"]`, which appears to
anticipate deletion of the committed credential (F-01). This baseline **does not touch
`pyproject.toml`**: the objective's authorized-path constraint is explicit and takes precedence,
and — more importantly — deleting the token from `HEAD` would not remediate the exposure, because
the value is preserved in reachable git history on a public remote. F-01 is therefore recorded as
the highest-priority finding with **rotation**, not deletion, as the required first action. See
[`06-stabilization-sequence.md` step 0](06-stabilization-sequence.md#step-0--rotate-the-exposed-eodhd-credential-p0).
