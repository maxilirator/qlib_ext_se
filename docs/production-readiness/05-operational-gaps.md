# 05 — Operational gaps

Baseline commit `77d8754`. This document covers what is missing to *operate* the package, as
distinct from the defects in [`04-failure-modes.md`](04-failure-modes.md) which cover what is wrong
with the code.

## 1. Release and distribution

| Capability | State | Consequence |
|---|---|---|
| Published artifact | None. No release workflow, no tag, no PyPI/registry presence | The consumer must depend on a git SHA or a local path |
| Versioning discipline | `0.1.0` in two hand-synced places (`pyproject.toml:7`, `__init__.py:10`); no SemVer policy | No signal for breaking changes on a surface that includes six unexported-but-used symbols |
| CHANGELOG | Absent | Upgrades cannot be reviewed |
| Wheel verification | Never performed in CI | F-02 (missing data file) has been latent since the package was created |
| Reproducible build inputs | No lockfile, no constraints file | Same commit can build differently on different days (F-14) |

The distribution gap is the operational root of two P0/P1 findings: because nothing ever builds and
inspects a wheel, the missing `xsto_trading_days_fallback.csv` was never noticed, and because there
is no release, the `requires-python` error would only be discovered by the consumer.

## 2. Observability

There is essentially no operational telemetry. What exists:

| Signal | Location | Level | Adequate? |
|---|---|---|---|
| "registered region" line | `region.py:89-97` | INFO | Emitted via `qlib.log`, wrapped in a blanket `except: pass` (`region.py:98`) — if qlib's logger is unavailable the registration is completely silent |
| `calendar_source=EODHD\|PMC\|EMBEDDED_CSV` | `calendar.py:123,132,142` | INFO | The single most useful line in the package. Emitted to the root `qlib_ext_se` logger with no configuration guidance in the README, and **not** emitted on a cache hit — the most common path |
| EODHD fetch failure | `calendar.py:86` | **DEBUG** | Effectively invisible (F-15) |
| Per-date parse failure | `calendar.py:71-72,82-83` | none | Silent |

Missing entirely: any metric or counter, any health/readiness signal, any way for the consumer to
ask "which calendar tier is currently in effect?", any structured field on the log lines beyond the
`extra=` dict in `region.py:91-96` (which standard formatters drop), and any record of the resolved
tier in the cache artefact.

**Operational consequence:** the three silent-degradation paths — EODHD → PMC (F-15), tier mixing
(F-16), and `$adjusted_close` → close (F-11) — are all invisible at default log level. Each changes
numbers rather than raising, which is the worst failure class for a trading stack.

## 3. Configuration and secrets

| Aspect | State |
|---|---|
| Key resolution order | `EODHD_API_KEY` env → `%APPDATA%/qlib-ext-se/config.toml` or `~/.config/qlib-ext-se/config.toml` (`config.py:31-47`). Documented consistently in `README.md:21-28` and `INSTRUCTIONS.md:33-37` |
| Secret in VCS | **Yes** — `pyproject.toml:43-44`, exposed since 2025-10-24 (F-01) |
| Secret scanning | No pre-commit hook, no CI secret scan, no `.gitleaks.toml` |
| Rotation procedure | Undocumented |
| Key validation | None — an invalid key is indistinguishable from no key (F-15) |
| Machine/service accounts | The user-scoped TOML path (`~/.config`) is a developer-workstation convention; there is no documented pattern for a service account or a container secret mount |

The resolution order itself is sound and correctly implemented. The gap is entirely in lifecycle:
the repository has no mechanism that would have prevented F-01 or that would detect a recurrence.

## 4. Deployment

`README.md:85` recommends installing this extension into a single trainer image rather than using
its own container, and that is the right call. But the repository still ships a `Dockerfile` whose
`CMD` cannot work (F-05), which leaves two contradictory deployment stories in the tree with no
statement of which is current.

Unaddressed deployment considerations:

- **Filesystem writability.** The cache path requires write access inside `site-packages` (F-07).
  A hardened image will break; nothing documents this requirement.
- **Network egress.** The EODHD tier makes an outbound HTTPS call to `eodhd.com` with a 20-second
  timeout (`calendar.py:59`), no retry, and no backoff. Air-gapped or egress-filtered environments
  are supported only by accident, via the silent PMC fallback.
- **Startup ordering.** F-08 is a deployment concern as much as a code concern: the consumer's
  process must call `register()` before `qlib.init`, and nothing in an image or manifest can
  enforce that.

## 5. Testing and quality gates

Detailed coverage table in
[`03-setup-test-run.md` §3](03-setup-test-run.md#coverage-reality). Operationally:

- No coverage measurement, so the gaps above are not visible to anyone reading CI output.
- No lint, format, or type-check gate. Annotations exist throughout but nothing checks them.
- No wheel-build or install-from-wheel job.
- No interpreter matrix — 3.9, 3.10 and 3.11 are nominally supported and never exercised.
- No test exercises the EODHD tier, the cache, or the embedded fallback tier.
- No integration test runs by default; `tests/test_dataset_smoke.py` needs `SE_PROVIDER_URI`, and
  no fixture bundle is provided or referenced.

## 6. Ownership and process

- Bus factor 1, no `CODEOWNERS`, no escalation path (F-22).
- No `AGENTS.md` or `CLAUDE.md`, despite one of the six commits being agent-authored — future agent
  contributors have no recorded conventions or boundaries.
- No issue templates, no PR template, no branch protection evidence in the workflow config.
- Three stale remote branches (`chore/flatten-ext-structure`, `copilot/create-qlib-ext-se-package`)
  remain alongside `main`.
- No documented support window for the `pyqlib==0.9.7` pin, and no plan for what happens when the
  consumer needs a newer qlib.

## 7. Gap summary by operational risk

| Gap | Risk if unaddressed | Priority |
|---|---|---|
| Secret lifecycle (no scanning, no rotation doc, live key in history) | Credential abuse, quota exhaustion presenting as silence | **Highest** |
| No wheel verification in CI | Ships a package missing its fallback data | **Highest** |
| Silent-degradation paths unmonitored | Wrong numbers with no alert | High |
| Cache writes into `site-packages` | Hard failure on hardened images | High |
| No lockfile / no upper bounds | Non-reproducible builds, surprise breakage | Medium |
| No coverage or lint gate | Regressions land unnoticed | Medium |
| Contradictory deployment story | Wasted operator time, false-green smoke test | Medium |
| Bus factor 1, no CODEOWNERS | No one accountable for a hard runtime dependency | Medium |
