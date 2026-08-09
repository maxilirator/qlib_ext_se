# 05 — Operational gaps

Gaps are recorded as *what is absent and what that absence costs*. Where a gap corresponds
to a finding in [04](04-failure-modes.md), the ID is given so remediation is not duplicated.

## 1. Release and versioning

| Question | Answer at `src` tree `6f1b143` (`77d8754`, `049f406`) |
|---|---|
| How is a release produced? | No procedure exists |
| Where is it published? | Nowhere — `qlib-ext-se` is not on PyPI (HTTP 404, E-14) |
| How do consumers get it? | `pip install git+…@main` — an unpinned branch (F-09) |
| Are there tags? | No release tags |
| Is there a changelog? | No (F-19) |
| Is the version single-sourced? | No — `pyproject.toml:7` and `__init__.py:10` (F-19) |

**Cost.** There is no unit of change that can be referenced, reviewed, or rolled back. The
consumer cannot express "the version of `qlib_ext_se` that worked last week", and a bad
commit here reaches the next consumer image build with no gate. Combined with F-08, the
release mechanism is also a hard blocker: the first version bump breaks the consumer's
dependency resolution, so **release must be solved before any fix ships**.

**Rollback.** There is no rollback path. Reverting means reverting `main` — the consumer
pins nothing else — which makes recovery a force-push-shaped problem rather than a pin
change.

## 2. Testing and quality gates

| Gate | Present? |
|---|---|
| Unit tests | Yes — 4 tests, 62% statements (E-15) |
| Failure-path tests | **No** — calendar tiers 1 and 3 are 0% covered (F-11) |
| Packaging test | **No** — F-02 is undetectable by the current suite |
| Integration test | Written but skipped; nothing sets `SE_PROVIDER_URI` (F-11) |
| Lint / format | **No** config of any kind in the tree |
| Type check | **No** |
| Interpreter matrix | **No** — 3.12 only, against a declared 3.9–3.12 range (F-15) |
| Container test | Nominally yes; runs zero tests (F-06) |
| Dependency audit | **No** |
| Secret scanning | **No** — F-01 has been in `main` since 2025-10-24 undetected, and is now carried by 7 commits reachable from `main` (E-05) |

**Cost.** CI is green and has been green through every finding in this document. The gate
answers "does it import and pass 4 tests on one interpreter", which is a much weaker
question than the badge implies. The two highest-value additions are a wheel-content
assertion (catches F-02, the P0) and secret scanning (would have caught F-01 at the
introducing commit).

## 3. Observability

`region.py:85-99` emits one structured `info` line on registration, with `region`,
`calendar`, `index`, `currency` — and wraps the whole thing in a bare `except: pass`, so a
logging misconfiguration silently removes the only registration signal.

`calendar.py` logs tier selection at `info` (`calendar_source=EODHD|PMC|EMBEDDED_CSV`), which
is genuinely useful — that field is the difference between an authoritative and a
synthesized calendar. But:

- Tier-1 **failures** log at `debug` (`calendar.py:86`), i.e. invisible in any normal
  configuration. A silent EODHD degradation is indistinguishable from EODHD never being
  configured (F-13).
- Cache **hits** log nothing at all (`calendar.py:115-116` returns early), so the tier field
  is absent exactly when a stale cached answer is being served (F-12).

Absent entirely: metrics, health checks, error reporting, and any versioned identity in the
logs — the registration line does not include `__version__`, so a log cannot be attributed
to a build. Given F-09, "which revision is running?" is unanswerable from telemetry.

**Cost.** The two most likely production incidents — a wrong calendar and a failed
registration — are the two least observable events. Cheapest fix with the largest return:
raise tier-1 failure logging to `warning`, log cache hits with the recorded source, and add
`__version__` to the registration line.

## 4. Secrets and credential handling

| Aspect | State |
|---|---|
| Credential in version control | **Yes** — `pyproject.toml:43-44`, public, since 2025-10-24 (F-01) |
| Is it read by the package? | No — nothing reads `pyproject.toml`; it is pure disclosure |
| Documented lookup path | `EODHD_API_KEY`, then user TOML (`config.py:31-48`) |
| Works on all supported interpreters? | No — TOML path inert on 3.9/3.10 (F-17) |
| Rotation procedure | None documented |
| Ownership | Split across both repositories, no single owner ([01 §5](01-architecture-and-ownership.md)) |
| Scanning / prevention | None |

**Cost.** A credential of unknown validity has been publicly readable for ~9.5 months, and
nothing in the toolchain would prevent or detect a recurrence. Note also that the
credential the repository *carries* is not the one the code *uses*, so anyone treating the
committed value as the configuration mechanism will find that changing it has no effect —
a small but real trap during incident response.

## 5. Deployment and runtime environment

This package has no deployment of its own; it is deployed as a dependency inside the
consumer's images. That inherited posture has four verified defects:

1. **The production install is lossy.** `pip install git+…` produces a wheel without the
   fallback calendar (F-02, E-06/E-07). Every consumer image is running a package that is
   missing a documented component.
2. **The arm64 images violate the version contract** and fail at `register()` (F-04,
   E-12/E-13).
3. **The runtime writes into `site-packages`** and dies on a read-only filesystem (F-03,
   E-11), which forecloses the standard container hardening.
4. **Builds are not reproducible** — moving `@main` ref, no lock file, unbounded dependency
   floors (F-09, F-14).

Defects 1 and 3 are shipped in every consumer image but are not currently *reachable* from
consumer code, because `register()` — the only symbol the consumer calls — touches no
calendar tier (E-19/E-20). That is containment by non-use, one import statement deep; see
[02 §5.4](02-cross-repository-interfaces.md). Defects 2 and 4 are reachable today.

The consumer's own Dockerfiles document two of these against themselves, in comments, as
known workarounds (`Dockerfile.gpu:61`, `Dockerfile.gpu.arm:57`). The gap is not awareness;
it is that neither repository owns closing them.

**Configuration surface.** The package reads exactly one environment variable
(`EODHD_API_KEY`) and one optional file. There is no way to override the cache location, the
trading hours, the calendar tier preference, or the pyqlib version gate. For a library this
minimal that is defensible, but the cache-location gap directly causes F-03.

## 6. Ownership and process

No `CODEOWNERS`, no `SECURITY.md`, no `CONTRIBUTING.md`; `authors = [{ name = "Your Team" }]`
is an unedited template (F-19). Every commit that touches runtime code is from a single
author on 2025-10-24; everything since is documentation from this initiative (E-01, E-22), so
the repository is dormant as far as the shipped package is concerned.

**Cost.** There is no route for a security report about F-01, no reviewer of record for
changes that flow straight into consumer images via `@main`, and a bus factor of one. The
cross-repository findings (F-04, F-08, F-09) each require a decision that neither repository
can make alone, and no forum exists in which to make them.

## 7. Gap summary

| Area | Severity | Blocking finding |
|---|---|---|
| Secrets | **Critical** | F-01 |
| Packaging / release | **Critical** | F-02, F-08 |
| Deployment reproducibility | High | F-04, F-09, F-14 |
| Runtime environment compatibility | High | F-03 |
| Test and quality gates | High | F-06, F-11, F-15 |
| Observability | Medium | F-13, F-12 |
| Ownership and process | Medium | F-19 |
