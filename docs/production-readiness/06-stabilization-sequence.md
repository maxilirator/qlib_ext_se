# 06 — Stabilization sequence

Baseline commit `77d8754`. Ordered remediation for the 22 findings in
[`04-failure-modes.md`](04-failure-modes.md). The ordering is deliberate: each step either removes
an active exposure, unblocks verification of later steps, or must precede work that would otherwise
be done twice.

**None of these steps were performed by this baseline.** The initiative is documentation-only and
authorizes changes under `docs/production-readiness/` alone. Each step below is a proposal with an
explicit exit criterion so completion can be verified independently.

---

## Step 0 — Rotate the exposed EODHD credential (P0)

**Addresses:** F-01 · **Blocking:** yes — do this before anything else, including before any commit
that touches `pyproject.toml`.

1. Rotate the token in the EODHD account console. The old value must be invalidated.
2. Re-provision the new token via `EODHD_API_KEY` or the user-scoped TOML — the two paths
   `config.py:31-47` actually reads.
3. Only then remove the `[eodhd]` table from `pyproject.toml:43-44`.
4. Decide explicitly on history: purge with `git filter-repo`/BFG and force-push, **or** record that
   the old value is permanently exposed and rely on step 1 having neutralised it. Either is
   defensible; leaving it undecided is not.
5. Audit EODHD account usage for the exposure window (2025-10-24 → rotation date) for unexpected
   consumption.

**Why first:** the token is live and the repository is public. Every later step is lower-value while
this stands, and step 3 alone accomplishes nothing without step 1.

**Exit criterion:** the old token returns an auth error from EODHD; `grep -rn "api_key" pyproject.toml`
is empty; the calendar EODHD tier still resolves in a test environment using the new token.

---

## Step 1 — Make the test suite honest and runnable (P1)

**Addresses:** F-03, F-04 · **Blocking:** yes — steps 2+ need a trustworthy signal.

1. `pyproject.toml:10` → `requires-python = ">=3.9,<3.13"`, matching pyqlib 0.9.7's actual wheel
   coverage ([E-02](evidence-log.md#e-02--pyqlib-097-distribution-availability)).
2. Add `pytest.importorskip("qlib")` at the top of `tests/test_register_basic.py`.
3. State the supported interpreter range in `README.md`.

**Exit criterion:** on a pyqlib-free Python 3.13, `pytest -q` reports `2 passed, 3 skipped` and exit
code 0. On Python 3.12 with `pip install -e .`, `pytest -q` reports `4 passed, 1 skipped`.

---

## Step 2 — Fix packaging so the shipped artifact is complete (P0)

**Addresses:** F-02 · **Blocking:** yes for any registry-based distribution.

1. Add to `pyproject.toml`:
   ```toml
   [tool.setuptools.package-data]
   qlib_ext_se = ["data/*.csv"]
   ```
2. Add a CI job that builds the wheel, installs it into a clean venv, and asserts the fallback file
   is importable-adjacent:
   ```python
   import importlib.resources as r, qlib_ext_se
   assert (r.files(qlib_ext_se) / "data" / "xsto_trading_days_fallback.csv").is_file()
   ```
3. While here, replace the `os.path.dirname(__file__)` lookup at `calendar.py:14-16` with
   `importlib.resources`, so the file resolves correctly from a zipped or relocated install.

**Exit criterion:** the E-05 wheel listing includes `qlib_ext_se/data/xsto_trading_days_fallback.csv`,
and the assertion above passes against a wheel install (not an editable one).

---

## Step 3 — Move the cache out of `site-packages` (P1)

**Addresses:** F-07 · **Depends on:** step 1.

1. Resolve the cache root in order: explicit `cache_dir` argument → `QLIB_EXT_SE_CACHE_DIR` →
   `XDG_CACHE_HOME/qlib-ext-se` → `~/.cache/qlib-ext-se`.
2. Make cache setup non-fatal: wrap `_ensure_cache_dir` so a `PermissionError`/`OSError` degrades to
   no-cache instead of aborting the call at `calendar.py:113`, before any tier has been tried.
3. Stop writing a file per single-date query — either widen the cache key to a coarse range (per
   calendar year is the natural unit) or have `is_trading_day` consult a range-level cache.
4. Delete `.gitignore:10` once the source tree can no longer be polluted.

**Exit criterion:** after `pytest -q`, `src/qlib_ext_se/_cache/` does not exist
([E-03](evidence-log.md#e-03--test-suite-execution) reproduced with the opposite result); the
calendar tests still pass with the cache directory forced to a read-only path.

---

## Step 4 — Make calendar sourcing explicit and observable (P1/P2)

**Addresses:** F-15, F-16, and the tier-selection half of F-06 · **Depends on:** step 3.

1. Return provenance. Either return a small result object carrying `(sessions, source)` or write a
   `source` column / sidecar into the cache. A cache hit must be able to state which tier produced
   it, and must log a `calendar_source=CACHE(<tier>)` line — today a cache hit logs nothing at all.
2. Accept empty tier-1 results as valid (`calendar.py:122`): a holiday-only range legitimately has
   zero sessions, and discarding it silently switches calendars mid-run.
3. Raise EODHD failure logging from DEBUG to WARNING (`calendar.py:86`), and distinguish
   "no key configured" (INFO, expected) from "key configured, call failed" (WARNING, actionable).
   Log the failure class.
4. Add a `source=` parameter so bundle generation can *demand* a tier and fail rather than silently
   degrade.
5. Add the first tests for this module: mock the EODHD response (success, 402, timeout, schema
   drift), exercise the cache, and exercise the embedded-CSV tier by forcing a PMC failure.

**Exit criterion:** for each of the four tiers there is a test asserting both the returned sessions
and the reported source; a forced EODHD failure emits a WARNING and reports `source="PMC"`.

---

## Step 5 — Model half-day sessions (P1)

**Addresses:** F-06 · **Depends on:** step 4.

The larger of the two sub-problems. XSTO had four early closes in 2025, verified at 13:00 local
against a 17:30 regular close ([E-06](evidence-log.md#e-06--xsto-regular-and-early-close-sessions)).

1. Replace the constant `se_trading_hours()` with a date-aware lookup, sourced from
   `pandas_market_calendars`' `early_closes(schedule)`.
2. Decide and **document** what the minute grid does on those dates. `_patch_time_utils`
   (`region.py:34-82`) builds `SE_TIME` **once** at registration, so a date-aware grid requires
   restructuring the patch, not just the helper. If the project only runs daily frequency, the
   defensible alternative is to document that minute-level SE support is out of scope and make
   `get_min_cal` raise for SE rather than return a silently wrong 510-slot grid.
3. In the EODHD tier, inspect the holiday record type and exclude only full closures; treat
   early-close entries as trading days.
4. Add a regression test asserting all four 2025 dates are present as sessions in every tier, and —
   if minute support is retained — that their session length is 240 minutes rather than 510.

**Exit criterion:** the four 2025 half-days are sessions in all four tiers; the intended minute-grid
behaviour is asserted by test and stated in `README.md`.

---

## Step 6 — Harden the cross-repository contract (P1/P2)

**Addresses:** F-08, F-11, F-13, F-12 · **Depends on:** step 1.

1. **Ordering (F-08).** Export `register_and_init(**qlib_init_kwargs)` that registers then calls
   `qlib.init`, and recommend it in `README.md` as the supported entry point. Add a test asserting
   that `qlib.init(region='se')` without `register()` raises `KeyError`, so the contract is pinned
   by test rather than by prose.
2. **Data contract (F-11).** Document in `README.md` that `deal_price="adjusted_close"` requires
   `$adjusted_close` in the provider bundle, and that a missing field degrades silently to close
   price. Raise this with `qlib-trading` so its bundle validator asserts the field.
3. **Rollback (F-13).** Remove `ensure_pyqlib_supported()` from `unregister()` (`region.py:116`), or
   wrap it, so the function honours its "best-effort" contract.
4. **Ownership tracking (F-12).** Record whether `register()` created `REG_SE` and the `"se"` region
   entry, and have `unregister()` reverse only what it installed; clear `_ORIGINALS`; guard both
   functions with a module-level `threading.Lock`.
5. Promote or delete the de-facto public surface: either add
   `build_xsto_trading_days`, `is_trading_day`, `se_trading_hours`, `get_eodhd_api_key` to `__all__`
   and treat them as versioned API, or mark them private. Today they are used without being
   declared ([`02` §3](02-cross-repository-interfaces.md#3-de-facto-public-surface-unexported-but-reachable)).

**Exit criterion:** `unregister()` on a pyqlib-free interpreter returns without raising; a test
pins the `KeyError` ordering contract; `README.md` states contracts C-1 … C-8 from
[`02` §5](02-cross-repository-interfaces.md#5-contract-imposed-on-the-qlib-trading-side).

---

## Step 7 — Supply chain and CI (P2/P3)

**Addresses:** F-14, F-20, and the CI half of F-05 · **Depends on:** steps 1–2.

1. Add upper bounds: `pandas>=2.0,<4`, `pandas-market-calendars>=4.3.2,<6`, and constrain
   `python-dateutil` / `pytz` / `requests`.
2. Commit a `constraints.txt` and have CI install with `-c constraints.txt`; refresh it deliberately.
3. Expand CI: interpreter matrix 3.9–3.12, pip caching, `concurrency` cancellation, a build-wheel
   job (step 2), ruff lint, coverage reporting.
4. Declare test dependencies as `[project.optional-dependencies] test = ["pytest"]` instead of
   installing pytest ad hoc in both CI and the Dockerfile.
5. Add secret scanning (gitleaks or GitHub secret scanning + push protection) so F-01 cannot recur.
6. Enable dependabot.

**Exit criterion:** CI is green across the 3.9–3.12 matrix; a deliberately reintroduced dummy secret
is blocked by the scanner.

---

## Step 8 — Resolve the deployment story (P1/P3)

**Addresses:** F-05, plus the contradiction noted in
[`05` §4](05-operational-gaps.md#4-deployment).

Pick one and remove the other:

- **Keep the Dockerfile:** add `COPY tests /app/tests` so the documented smoke test actually runs.
- **Delete it:** consistent with the guidance already in `README.md:85` that the extension should be
  installed into a single trainer image. This is the recommended option — the Dockerfile provides no
  value beyond a test runner that CI already covers.

**Exit criterion:** either `docker build . && docker run --rm <img>` exits 0 having run the calendar
tests, or the Dockerfile is gone and `README.md` states the trainer-image approach as the only one.

---

## Step 9 — Documentation and hygiene (P3)

**Addresses:** F-10, F-17, F-18, F-19, F-21, F-22.

1. **F-21 first** — it is the highest-value documentation fix. State plainly in `README.md` that
   `register()` does **not** install a calendar into qlib, that qlib's trading days come from the
   provider bundle's `calendars/day.txt`, and that `build_xsto_trading_days` is an offline
   bundle-generation utility.
2. `normalize_symbol` (F-18): fix it to preserve share-class hyphens (`ERIC-B.ST`, not `ERICB.ST`)
   with tests, or delete it and strike the claim at `INSTRUCTIONS.md:21`.
3. Note in `INSTRUCTIONS.md` that the `REG_SE` constant patch is cosmetic (F-10).
4. Add `py.typed`, `CHANGELOG.md`, `CODEOWNERS`, and an `AGENTS.md` recording repository conventions
   (F-17, F-22). Single-source the version to remove the `pyproject.toml`/`__init__.py` duplication.
5. Replace `authors = [{ name = "Your Team" }]` (F-19).
6. Delete the two stale remote branches.

**Exit criterion:** a new integrator reading only `README.md` can correctly answer: which Python
versions are supported, what the bundle must contain, which symbols are API, what `register()` does
and does not install, and who owns the repository.

---

## Sequencing rationale

```
Step 0  rotate credential            ── unblocks everything; exposure is live
  │
Step 1  test suite honest/runnable   ── all later verification depends on a trustworthy suite
  │
  ├─ Step 2  packaging (wheel data)  ── P0; independent of 3–6
  │
Step 3  cache relocation             ── prerequisite for 4 (cache gains provenance)
  │
Step 4  calendar provenance + logs   ── prerequisite for 5 (half-days need per-tier control)
  │
Step 5  half-day sessions            ── largest correctness fix; touches the patch structure
  │
Step 6  contract hardening           ── independent of 3–5; can run in parallel after step 1
  │
Step 7  supply chain + CI            ── needs 1–2 to be meaningful
Step 8  deployment story             ── independent
Step 9  documentation                ── last, so it describes the fixed state
```

## Definition of "production-ready" for this package

The package can be considered production-ready when all of the following hold:

1. No credential exists in the working tree or in reachable history that has not been rotated.
2. A wheel built from `main`, installed into a clean venv, resolves all four calendar tiers.
3. CI is green on the full supported interpreter matrix, with a wheel-verification job.
4. The four 2025 XSTO half-days behave correctly in every calendar tier, and the minute-grid
   behaviour on those dates is asserted by test.
5. Every silent-degradation path (EODHD→PMC, tier mixing, `$adjusted_close`→close) emits a WARNING
   and is observable by the operator.
6. Contracts C-1 … C-8 are stated in `README.md` and, where testable, pinned by test.
7. The calendar cache works on a read-only, non-root container.
8. A second named owner exists in `CODEOWNERS`.

Against this definition, the current state satisfies **none of the eight**.
