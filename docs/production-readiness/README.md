# Production-readiness baseline — `qlib_ext_se`

**Date of assessment:** 2026-08-09 (round 1) · **re-verified 2026-08-09 (round 2)**
**Runtime revision assessed:** `src` tree `6f1b143`, `tests` tree `d91f05a` — identical at
`77d8754`, at `049f406` (tip of `main`), and on this documentation branch. The tree hashes,
not a commit SHA, are the durable identity: every documentation commit changes `HEAD` while
leaving the assessed code byte-identical (E-22).
**Consumer revision referenced:** `qlib-trading` `16425ce` (tip of `main`, 2026-08-09
21:19:58 +0200). Its `src`, `scripts`, `tests`, `docker` and `pyproject.toml` trees are
byte-identical to `c8e7c4b`, the SHA used in round 1, so every consumer citation in
[02](02-cross-repository-interfaces.md) resolves under **both** (E-22).
**Scope:** this repository (`qlib_ext_se`) and its side of the interface with the consuming
repository `qlib-trading`.
**Method:** every claim below is reproduced from repository evidence, executed in a
disposable environment. Commands and raw output are in [`evidence-log.md`](evidence-log.md).

This baseline is documentation only. No runtime code, configuration, deployment state,
credential, or external service was modified by this work.

## What this repository's contribution can and cannot establish

The initiative spans two repositories plus a final operational step. This document set is
the `qlib_ext_se` half. Stating the split precisely is part of the deliverable — an absent
item below is not a defect in this contribution.

| Initiative criterion | This repository establishes | Owned elsewhere |
|---|---|---|
| **`qlib-ext-se-architecture`** — accurate baseline of package boundaries, data contracts, Qlib integration points, setup, tests, known limitations | **Fully.** [01](01-architecture-and-ownership.md) (module map, `register()` path, calendar tiers, ownership table), [03](03-setup-test-run.md) (executed setup/test/run), [04](04-failure-modes.md) (limitations, F-01…F-19) | — |
| **`cross-repo-contract`** — dependency direction, integration contracts, version assumptions, failure propagation | **The provider half, verified against a pinned consumer checkout.** [02](02-cross-repository-interfaces.md): direction (§1), C-1…C-9 (§3), V-1…V-7 (§4), P-1…P-10 (§5), and §8, which answers the five provider guarantees the `qlib-trading` baseline explicitly delegates here | Consumer-side remediation (§7): `--no-deps`, `@main` pins, the shared import guard at `qlib_data_connector.py:24-31`, post-registration assertions. Listed, not fixed here |
| **`readiness-risks`** — reproducible setup/test/run, evidence-backed prioritized failure register, unresolved gaps, ordered stabilization plan | **Fully, for this package.** [03](03-setup-test-run.md), [04](04-failure-modes.md), [05](05-operational-gaps.md), [06](06-stabilization-sequence.md) | Fleet-level questions — which images are deployed, on which architecture, whether any minute-frequency path is live — need a running system (§"Not establishable" below) |
| **`qlib-trading-architecture`** — the consumer's own components, entry points, data flow, external interfaces | **Nothing.** Out of scope for this repository | `maxilirator/qlib-trading` — `docs/production-readiness/qlib-trading-baseline.md` at `16425ce` |

**Not establishable in either repository** (needs a built and running consumer image):
whether an arm64 build actually reaches the P-2 `RuntimeError` in production; which images
are currently deployed and on which architecture; whether any minute-frequency path is live;
and which provider revision produced each historical research artifact — which, per
[02 §5.6](02-cross-repository-interfaces.md), is **not recoverable** for runs already
completed.

## Documents

| Document | Contents |
|---|---|
| [01 — Architecture and ownership](01-architecture-and-ownership.md) | Module map, the `register()` runtime path, ownership boundaries |
| [02 — Cross-repository interfaces](02-cross-repository-interfaces.md) | Dependency direction, declared vs. de-facto API, contracts C-1…C-9, version assumptions V-1…V-7, failure propagation P-1…P-10, remediation ownership, provider guarantees G-1…G-5 |
| [03 — Setup, test, run](03-setup-test-run.md) | Reproducible procedures, executed and timed; coverage reality |
| [04 — Failure modes](04-failure-modes.md) | 19 findings, F-01…F-19, ranked P0–P3 |
| [05 — Operational gaps](05-operational-gaps.md) | Release, observability, secrets, deployment, ownership |
| [06 — Stabilization sequence](06-stabilization-sequence.md) | Ordered remediation with exit criteria |
| [evidence-log.md](evidence-log.md) | E-01…E-24: every command with its output |

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
   It does not reach the consumer *today*, and the reason is narrow: `register()` — the only
   symbol the consumer uses — touches no calendar tier (E-19/E-20). The defect is contained by
   non-use, not by design; one import statement in the consumer activates it.
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
are installed (E-03, re-run in E-22). It covers 62% of statements, and 0% of the two calendar
tiers that matter under failure (E-15).

## Round-2 re-verification

Round 2 re-executed the round-1 evidence rather than restating it. Outcome (E-22):

- **Every round-1 measurement reproduced exactly** — test result, coverage table, wheel
  contents, calendar parity, early closes, register/unregister behaviour, the version gate,
  the PyPI 404, the container smoke test, the TOML guard, `normalize_symbol` divergence, and
  all 30 consumer call sites across 28 files.
- **Five evidence defects were repaired**, all in the record rather than in the findings:
  the coverage command was not reproducible as written (it yields 52%, not 62%, against a
  warm `_cache` — E-15); the lock-file check in E-19 used `git ls-files <sha>`, which cannot
  detect lock files at all and would have reported `0` either way (the corrected command
  gives the same answer); the credential now sits in 7 commits reachable from `main`, not 5,
  because documentation commits carry `pyproject.toml` forward (E-05); the `PermissionError`
  in E-11 has two distinct sites depending on whether `_cache` already exists (F-03); and the
  CI history in E-01 predates this initiative's own runs.
- **Two findings gained executed evidence** where round 1 argued from code reading: calendar
  tier 1 is now exercised end-to-end with a stubbed holiday set, and its divergence from tier
  2 is quantified — an empty holiday response yields **261 trading days for 2025 against the
  exchange's 249**, i.e. 12 fabricated sessions including 2025-01-01 and 2025-05-01 (E-23,
  F-13).
- **The five provider guarantees the consumer baseline delegates here** are answered
  individually with evidence in [02 §8](02-cross-repository-interfaces.md) (G-1…G-5).

No finding was added, removed, or re-prioritised by round 2.

## Verification status per initiative criterion

| Required criterion | Status | Where |
|---|---|---|
| Architecture and ownership boundaries | Verified; re-verified at the pinned tree | [01](01-architecture-and-ownership.md), E-22 |
| Cross-repository dependency direction, integration contracts, version assumptions, and failure propagation | Provider half verified against `qlib-trading` `16425ce` (identical code at `c8e7c4b`); every consumer citation re-derived in round 2 | [02](02-cross-repository-interfaces.md), E-19/E-20/E-22 |
| Reproducible setup / test / run procedures | Executed end-to-end, not merely described; coverage procedure corrected in round 2 | [03](03-setup-test-run.md), E-01…E-04, E-22 |
| Prioritized failure modes | 19 findings, each with a reproduction; F-13 upgraded from reasoning to measurement | [04](04-failure-modes.md), E-23 |
| Operational gaps | Verified | [05](05-operational-gaps.md) |
| Stabilization sequence | Ordered, with exit criteria | [06](06-stabilization-sequence.md) |
| Consumer-side architecture and ownership | **Not this repository's to establish** | `qlib-trading` `docs/production-readiness/` |
| Integrated, running-system behaviour | **Not establishable from either checkout** | Final operational verification |

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
interpreter it is green (E-03, E-22). The related genuine finding is narrower and is recorded
as F-05: `requires-python = ">=3.9"` has no upper bound, so the package advertises support for
interpreters on which its own pinned dependency cannot be installed (E-04).
