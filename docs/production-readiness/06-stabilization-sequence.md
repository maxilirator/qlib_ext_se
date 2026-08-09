# 06 — Stabilization sequence

An ordered remediation plan. Ordering is driven by two dependencies discovered during the
assessment, not by severity alone:

- **F-08 gates every versioned change.** The consumer declares `qlib-ext-se>=0.1.0` against
  a distribution that is not published anywhere (E-14). Today that resolves only because
  0.1.0 happens to be installed already. Raise this package's version before fixing the
  release mechanism and the consumer's image build breaks. So release comes early, before
  the code fixes that would otherwise be first.
- **F-01 is remediated outside this repository.** Rotation at EODHD is the only action that
  changes the security posture; no commit here does. It therefore runs in parallel with
  everything else and blocks nothing.

Each step lists an exit criterion that can be checked mechanically. Effort is
order-of-magnitude only.

---

## Step 0 — Rotate the EODHD credential *(F-01, immediate, out-of-repo)*

Runs first and in parallel; nothing waits on it.

1. Rotate the token in the EODHD account. Assume disclosure: it has been readable in a
   public repository since 2025-10-24 (E-05).
2. Review the account's usage history for the exposure window, if EODHD exposes it.
3. Distribute the new token through the supported path only — `EODHD_API_KEY`, or the user
   TOML file — **never** `pyproject.toml`.
4. Delete `pyproject.toml:43-44` in this repository. This is hygiene, not remediation: the
   value remains in public history at `55327d9`, and rewriting history does not retract
   what has already been cloned or indexed.
5. Enable push-time secret scanning so the class of defect cannot recur.

**Do not** treat removing the line as the fix, and do not spend effort on history rewriting
in place of rotation.

**Exit criterion:** the committed value is rejected by EODHD; `git grep` at `HEAD` finds no
credential; secret scanning is enabled and passing.

**Effort:** hours. **Owner:** whoever holds the EODHD account.

---

## Step 1 — Establish a release mechanism *(F-08, F-09, F-19)*

Everything versioned depends on this. Nothing here changes runtime behaviour, so it is safe
to do first.

1. Decide the distribution channel and write it down: publish `qlib-ext-se` to an index the
   consumer's builds can reach, **or** standardise on a direct git reference
   (`qlib-ext-se @ git+https://…@<tag>`) in the consumer's `pyproject.toml`. Either is
   defensible; the current half-state — a PyPI-style constraint satisfied by a git install
   — is not.
2. Single-source the version (`dynamic = ["version"]`), add `CHANGELOG.md`, tag `v0.1.0` at
   the current `main` so there is a named baseline to roll back to.
3. Change the consumer's Dockerfiles from `@main` to the tag.
4. Set a real `authors` value; add `CODEOWNERS` and `SECURITY.md`.

**Exit criterion:** a consumer image builds from a tagged revision with no `@main` reference
anywhere; bumping this package's version and the consumer's floor together succeeds in a
test build.

**Effort:** 1–2 days, spanning both repositories.

---

## Step 2 — Fix packaging so installs are complete *(F-02, plus the test that keeps it fixed)*

The P0 code defect. Small change, large blast radius, and it must not regress.

1. Add to `pyproject.toml`:
   ```toml
   [tool.setuptools.package-data]
   "qlib_ext_se" = ["data/*.csv"]
   ```
2. Add a packaging test that builds a wheel and asserts the CSV is inside it, and add the
   wheel build to CI. **This test is the deliverable**, not the one-line config change —
   without it the defect silently returns, exactly as it did undetected for 9.5 months.
3. Add a tier-3 test: force tier 2 to fail and assert the embedded snapshot answers (this is
   the reproduction already used in E-07).
4. Add the parity assertion from E-08 — embedded CSV versus `pandas-market-calendars` XSTO,
   zero divergence — so the repository's strongest asset stays verified.
5. Correct `README.md:30` to state the real range and session count (F-18).

**Exit criterion:** `python -m build --wheel` produces a wheel containing
`qlib_ext_se/data/xsto_trading_days_fallback.csv`; a fresh wheel install reports
`fallback present: True`; CI fails if either regresses.

**Effort:** half a day.

---

## Step 3 — Make the runtime container-safe *(F-03, F-12)*

Unblocks read-only filesystems and stops the package writing into itself.

1. Resolve the cache to a user/state directory — `XDG_CACHE_HOME`, else
   `~/.cache/qlib-ext-se` — with an explicit environment override.
2. Make cache failure non-fatal: a write error must degrade to recomputation, never raise.
   Note `_ensure_cache_dir()` is currently called at `calendar.py:113` *before* any tier is
   attempted, so a permission error defeats all three fallbacks.
3. Key the cache per year rather than per `(start, end)` pair, so `is_trading_day` stops
   creating one file per date.
4. Record the producing tier and fetch time inside each cache file, and add a TTL.

**Exit criterion:** with the installed package directory read-only,
`build_xsto_trading_days` returns sessions (reproduction E-11 passes instead of raising);
repeated `is_trading_day` calls across a month create O(1) cache files.

**Effort:** 1 day.

---

## Step 4 — Resolve the pyqlib version contract *(F-04, F-05, F-17)*

A cross-repository decision. Do not relax the gate as a convenience — the pin exists because
this package patches pyqlib internals that carry no compatibility promise.

1. Decide, jointly with `qlib-trading`: either support a tested pyqlib range, or drop arm64.
2. If widening: validate each patch point (`qlib.constant`, `qlib.config._default_region_config`,
   `qlib.utils.time.get_min_cal`, `.time_to_day_index`) against every version admitted, and
   add them to the CI matrix. A version admitted without an exercised patch point is worse
   than the current hard failure, because it fails silently instead of loudly.
3. If dropping arm64: remove the `--no-deps` workaround from `Dockerfile.gpu.arm` and the
   `aarch64→0.9.3` defaults in the other GPU Dockerfiles, so the conflict surfaces at build
   time rather than at `register()`.
4. Set `requires-python = ">=3.9,<3.13"` to match the dependency's real wheel coverage
   (F-05).
5. Resolve the 3.9/3.10 TOML gap (F-17): add `tomli; python_version < "3.11"`, or raise the
   floor to `>=3.11` and delete the guard in `config.py:6-9`. Raising the floor is simpler
   and consistent with the interpreter narrowing above.

**Exit criterion:** no image installs a pyqlib version the gate rejects; `register()` is
exercised in CI on every admitted pyqlib/interpreter combination; installing on an
unsupported interpreter fails with an error naming *this* package.

**Effort:** 2–3 days, spanning both repositories.

---

## Step 5 — Close the test and CI gaps *(F-11, F-06, F-15)*

1. Cover the EODHD tier with a stubbed HTTP response — both documented response shapes, plus
   the failure path — since it is 0% covered today and is the *preferred* tier whenever a
   key exists.
2. Assert directly on the patched functions' output (`region.py:55-76`, currently installed
   but never called by any test), including minute-bar counts.
3. Test `normalize_symbol`, or delete it (see Step 6).
4. Fix the container: `COPY tests /app/tests`, or drop the `CMD` and its "smoke test"
   comment rather than shipping an image that claims a guarantee it cannot provide.
5. Add a CI interpreter matrix across the supported range, and a lint/format configuration.

**Exit criterion:** every calendar tier and both patched functions have a direct test;
`docker run <image>` executes a non-zero number of tests and exits 0; CI runs the full
matrix.

**Effort:** 2 days.

---

## Step 6 — Correct the calendar and interface semantics *(F-07, F-13, F-10, F-16)*

Correctness work that needs the test scaffolding from Steps 2 and 5 to be safe.

1. **Early closes (F-07).** Derive session hours per date from the exchange schedule rather
   than the constant in `se_trading_hours()`. `pandas-market-calendars` already returns
   `market_open`/`market_close` per session at the point tier 2 is read. Until this lands,
   document the daily-frequency-only constraint prominently — the current failure is silent
   fabrication of 270 phantom minute bars on early-close days (E-09, E-10).
2. **Tier semantics (F-13).** Raise tier-1 failure logging from `debug` to `warning`;
   validate that a multi-month Swedish range returns a non-empty holiday set; log cache hits
   with the recorded source; and reconsider the tier ordering so the maintained exchange
   schedule is authoritative and EODHD is the cross-check rather than the default.
3. **Symbol normalization (F-10).** Decide ownership and remove the duplicate. If the
   extension's version stays, fix the `.XSTO` suffix bug (`'ABB.XSTO'` → `'ABB.XSTO.ST'`),
   test it, and migrate the consumer. If it goes, delete it and correct `INSTRUCTIONS.md:21`,
   which currently advertises it as part of the hand-off contract.
4. **`unregister()` ownership (F-16).** Record in `_ORIGINALS` whether `register()` actually
   created each entry, and remove only what was created.

**Exit criterion:** minute-bar counts match the exchange schedule on the 2025 early-close
dates; a simulated EODHD degradation logs at warning and does not silently yield
Mon–Fri-everything; exactly one `normalize_symbol` exists in the stack.

**Effort:** 3–4 days.

---

## Step 7 — Dependency and observability hardening *(F-14, F-19, observability)*

1. Add upper bounds to the direct dependencies and commit a lock file used by CI and image
   builds. Starting point in E-02: pyqlib 0.9.7, pandas 2.3.3, numpy 2.5.2,
   python-dateutil 2.9.0.post0, pytz 2026.3.post1, requests 2.34.2.
2. Add `__version__` to the registration log line so a running build is identifiable from
   telemetry.
3. Add `py.typed` if the annotations are intended to be public.

**Exit criterion:** two builds of the same commit resolve to identical dependency sets; logs
identify the package version.

**Effort:** 1 day.

---

## Sequence summary

| Step | Findings | Blocks | Effort |
|---|---|---|---|
| 0 — Rotate credential | F-01 | nothing (parallel) | hours |
| 1 — Release mechanism | F-08, F-09, F-19 | **every later step** | 1–2 d |
| 2 — Packaging + tests | F-02, F-18 | — | 0.5 d |
| 3 — Container-safe runtime | F-03, F-12 | — | 1 d |
| 4 — pyqlib contract | F-04, F-05, F-17 | — | 2–3 d |
| 5 — Test and CI gaps | F-11, F-06, F-15 | Step 6 | 2 d |
| 6 — Calendar/interface semantics | F-07, F-13, F-10, F-16 | — | 3–4 d |
| 7 — Dependencies, observability | F-14, F-19 | — | 1 d |

Steps 2 and 3 are independent of each other and of Step 4; they can run concurrently once
Step 1 lands. Step 6 should follow Step 5 so the corrections are made against a suite that
can detect a regression.

### Which steps close the guarantees `qlib-trading` is waiting on

The consumer's baseline blocks its own promotion on five provider guarantees, answered
individually in [02 §8](02-cross-repository-interfaces.md). Two already hold; the other three
are closed by the steps above, and this is the order in which the consumer will see them:

| Guarantee | Status today | Closed by |
|---|---|---|
| G-2 registration idempotency | **holds** (E-10, E-20) | — keep it holding: it is the only contract the consumer actually exercises |
| G-4 reverse-import absence | **holds** (E-24) | — |
| G-5 tested/pinned revision | no tag, no published artifact | **Step 1**, and nothing the consumer can do first |
| G-3 package data / calendar | wheel omits the fallback CSV | **Step 2**, then Step 6 for session hours and tier semantics |
| G-1 pyqlib/Python matrix | pyqlib 0.9.7 + CPython 3.12 only, declared range wider | **Step 4**, jointly with the consumer |

Steps 1 and 2 are therefore the two that unblock the *other* repository, and they are also
the cheapest. Nothing in the consumer's stabilization sequence can proceed past its own
"freeze identities" gate until Step 1 produces something to pin.

## Definition of "production-ready" for this package

Derived from the findings, so completion is checkable rather than a judgement call:

1. No credential in the repository or its history is valid.
2. A wheel built from a tagged revision contains every file the runtime needs, verified in CI.
3. Every deployed image installs a pyqlib version the gate accepts, verified at build time.
4. The package runs on a read-only filesystem as a non-root user.
5. Every calendar tier, including both failure paths, has a direct test.
6. Session hours are derived from the exchange schedule, or the minute path is documented as
   unsupported.
7. Consumer images pin a tagged revision, and two builds of one commit are identical.
8. A calendar-source degradation is visible at `warning` or above.
