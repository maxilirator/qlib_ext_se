# Production-readiness baseline — `qlib_ext_se`

**Date of assessment:** 2026-08-09
**Commit assessed:** `77d8754` (`main`)
**Scope:** this repository (`qlib_ext_se`) and its interface with the consuming
repository `qlib-trading`.
**Method:** every claim below is reproduced from repository evidence, executed in a
disposable environment. Commands and raw output are in [`evidence-log.md`](evidence-log.md).

This baseline is documentation only. No runtime code, configuration, deployment state,
credential, or external service was modified by this work.

## Documents

| Document | Contents |
|---|---|
| [01 — Architecture and ownership](01-architecture-and-ownership.md) | Module map, the `register()` runtime path, ownership boundaries |
| [02 — Cross-repository interfaces](02-cross-repository-interfaces.md) | Dependency direction, declared vs. de-facto API, contracts C-1…C-9 |
| [03 — Setup, test, run](03-setup-test-run.md) | Reproducible procedures, executed and timed; coverage reality |
| [04 — Failure modes](04-failure-modes.md) | 19 findings, F-01…F-19, ranked P0–P3 |
| [05 — Operational gaps](05-operational-gaps.md) | Release, observability, secrets, deployment, ownership |
| [06 — Stabilization sequence](06-stabilization-sequence.md) | Ordered remediation with exit criteria |
| [evidence-log.md](evidence-log.md) | E-01…E-16: every command with its output |

## Executive assessment

`qlib_ext_se` is a small, single-purpose package: 6 Python modules, 229 executable
statements, one data file. It monkey-patches `pyqlib` 0.9.7 at runtime so that
`region="se"` becomes a usable Qlib region. Its scope is well chosen, its public
surface is genuinely small, and the parts that are tested are correct.

**It is not production-ready as packaged.** The defects are not in the algorithm — the
Stockholm calendar data is exact — they are in packaging, dependency contracts, and the
boundary with the consuming repository. Three verified facts carry most of the risk:

1. **The wheel does not contain the calendar fallback data.** `data/xsto_trading_days_fallback.csv`
   is excluded from every non-editable install because `qlib_ext_se.data` is not a
   package and no package-data rule declares it. The consuming repository installs this
   package exactly that way — `pip install git+https://github.com/maxilirator/qlib_ext_se.git@main`
   in its production Dockerfiles. In those images the documented last-resort calendar tier
   does not exist, and a `pandas-market-calendars` failure propagates instead of degrading. (F-02, E-06/E-07)
2. **An EODHD API token is committed to this public repository** and has been since
   2025-10-24. It is present at `HEAD` in `pyproject.toml:43-44`. (F-01, E-05)
3. **The pinned dependency contract is violated by the consumer on one architecture.**
   `qlib_ext_se` hard-fails on any `pyqlib` other than exactly 0.9.7; the consumer's
   arm64 images install `pyqlib==0.9.3` and then install this package with `--no-deps`,
   so the conflict is not detected at build time and surfaces as a `RuntimeError` from
   `register()` at runtime. (F-04, E-12/E-13)

Counterweight: the embedded calendar is **exactly correct**. All 9,041 sessions from
2000-01-03 to 2035-12-28 match `pandas-market-calendars` XSTO with zero divergence in
either direction (E-08). `register()` is idempotent and `unregister()` fully restores the
patched functions (E-10). Those are the load-bearing behaviours and they hold.

The test suite passes — 4 passed, 1 skipped — when the package's declared dependencies
are installed (E-03). It covers 62% of statements, and 0% of the two calendar tiers that
matter under failure (E-15).

## Verification status per initiative criterion

| Required criterion | Status | Where |
|---|---|---|
| Architecture and ownership boundaries | Verified | [01](01-architecture-and-ownership.md) |
| Cross-repository interfaces and dependency direction | Verified against the consumer checkout | [02](02-cross-repository-interfaces.md) |
| Reproducible setup / test / run procedures | Executed end-to-end, not merely described | [03](03-setup-test-run.md), E-01…E-04 |
| Prioritized failure modes | 19 findings, each with a reproduction | [04](04-failure-modes.md) |
| Operational gaps | Verified | [05](05-operational-gaps.md) |
| Stabilization sequence | Ordered, with exit criteria | [06](06-stabilization-sequence.md) |

## Two claims this baseline deliberately does **not** make

These are stated explicitly because a previous revision of this baseline overstated both.

**The committed token's validity is unverified.** This assessment did not send the token
to EODHD. Testing a third party's credential against a live external service is outside
the read-only scope of this work and would consume that account's quota. What repository
evidence establishes is: a credential-shaped string is committed, in a public repository,
since 2025-10-24, and it is still present at `HEAD`. Whether it currently authenticates is
unknown and is not needed to justify the remediation — a committed credential of unknown
status in public history must be rotated regardless. F-01 is scoped to exactly that.

**The test suite has no defect that makes it fail.** The suite fails only when the
mandatory dependency `pyqlib==0.9.7` (declared at `pyproject.toml:20`) is absent. That is
an environment condition, not a test bug. With the dependency installed on a supported
interpreter it is green (E-03). The related genuine finding is narrower and is recorded as
F-05: `requires-python = ">=3.9"` has no upper bound, so the package advertises support for
interpreters on which its own pinned dependency cannot be installed (E-04).
