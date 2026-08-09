# 04 — Prioritized failure modes

19 findings against `src` tree `6f1b143` / `tests` tree `d91f05a` — identical at `77d8754`
and at `049f406`, tip of `main` (E-22). Every finding has a reproduction in
[`evidence-log.md`](evidence-log.md); none is inferred from documentation alone. Round 2
re-executed every reproduction and added none, removed none, and re-prioritised none; two
findings (F-03, F-13) gained sharper evidence and are marked below.

Priority is assigned by *reachability in the consumer's actual deployment path*, not by
theoretical severity. A defect that only manifests in an install method nobody uses ranks
below one that is live in production images today.

| ID | Priority | Finding |
|---|---|---|
| F-01 | P0 | EODHD API token committed to a public repository |
| F-02 | P0 | Wheel and git installs omit the fallback calendar data |
| F-03 | P1 | Calendar cache is written inside the installation directory |
| F-04 | P1 | pyqlib exact-pin is bypassed on arm64 images; `register()` fails at runtime |
| F-05 | P1 | `requires-python` has no upper bound |
| F-06 | P1 | The container "smoke test" runs zero tests |
| F-07 | P1 | XSTO early-close days are not modelled |
| F-08 | P1 | `qlib-ext-se` is unpublished; the consumer's constraint breaks on any version bump |
| F-09 | P1 | Consumer images install from the moving `@main` ref |
| F-10 | P2 | Divergent duplicate `normalize_symbol`; `.XSTO` suffix mishandled |
| F-11 | P2 | Both failure-path calendar tiers and both patched functions are untested |
| F-12 | P2 | Cache key produces one file per queried date, with no invalidation or provenance |
| F-13 | P2 | Calendar tiers 1 and 2 compute sessions on different bases; tier-1 errors are swallowed |
| F-14 | P2 | No lock file; direct dependencies are floor-pinned only |
| F-15 | P2 | CI does not build a wheel, lint, type-check, or test a matrix |
| F-16 | P2 | `unregister()` removes state it may not own |
| F-17 | P3 | The TOML credential path is silently inert on Python 3.9/3.10 |
| F-18 | P3 | README understates the embedded calendar's coverage |
| F-19 | P3 | Repository hygiene: no CHANGELOG, CODEOWNERS, SECURITY.md, or `py.typed`; version dual-sourced |

---

## P0

### F-01 — EODHD API token committed to a public repository

**Location:** `pyproject.toml:43-44`

```toml
[eodhd]
api_key = "68ed7524…"          # redacted here; full value is in the file and in git history
```

**Evidence (E-05):**

- `gh repo view` reports `"visibility":"PUBLIC"`.
- The value first appears in commit `55327d9`, 2025-10-24 22:38:41 +0200, at
  `ext/qlib-ext-se/pyproject.toml`, and survives the repository flattening into
  `pyproject.toml` at `HEAD`. Exposure to date: ~9.5 months.
- It is present in **7 commits reachable from `main`** and 8 across all refs (E-05, re-counted
  in round 2). Round 1 recorded 5; the count grows with every commit that carries
  `pyproject.toml` forward, including this baseline's own documentation commits — which is
  itself a small illustration of why deletion at `HEAD` is not remediation.

**What is verified and what is not.** Verified: a credential-shaped string is committed, in
a public repository, and is present at `HEAD`. **Not verified: whether the token currently
authenticates.** This assessment deliberately did not send it to EODHD — exercising a third
party's credential against a live external service is outside the read-only scope of this
work and would consume that account's quota. The remediation does not depend on the answer.

**Also verified: the token is inert within this package.** `config.py:31-48` reads
`EODHD_API_KEY` and `~/.config/qlib-ext-se/config.toml`. Nothing in `src/` or `tests/` reads
`pyproject.toml`; the only match for `[eodhd]` outside the file itself is the docstring at
`config.py:36`. So this token does not participate in calendar tier 1 — it is pure
disclosure, not a functional dependency. Removing it changes no behaviour.

**Failure scenario:** if the token is or was valid, any reader of the public repository
between 2025-10-24 and rotation can call EODHD as this account — consuming quota,
triggering rate limits that degrade the consumer's `scripts/eodhd_sync.py` data pulls, and
exposing whatever entitlements the account carries.

**Remediation:** rotate at EODHD first. Deleting the line from `HEAD` does not remediate —
the value remains in public history at `55327d9` and its descendants, and history rewriting
does not retract what has already been cloned or indexed. Rotation is the only action that
changes the security posture; removing the line afterwards is hygiene.

---

### F-02 — Wheel and git installs omit the fallback calendar data

**Location:** `pyproject.toml:32-37`; `calendar.py:14-16,137-149`

`data/xsto_trading_days_fallback.csv` is absent from every built distribution.
`qlib_ext_se.data` contains no `__init__.py`, so
`[tool.setuptools.packages.find] include = ["qlib_ext_se*"]` does not discover it as a
package, and there is no `package-data`, `include-package-data = true`, or `MANIFEST.in`.

**Evidence (E-06):** the built wheel contains six `.py` files and the `dist-info`, and
nothing else — `CSV present in wheel: False`.

**Evidence (E-07):** in a clean venv with the wheel installed, `_FALLBACK_CSV` does not
exist, and with tier 2 forced to fail the exception propagates:

```
fallback EXISTS: False
RESULT: RAISED RuntimeError simulated PMC outage
```

**Why this is P0 rather than a packaging nit:** this is the install method the consumer
uses in production. Every `qlib-trading` GPU/CPU Dockerfile runs
`pip install git+https://github.com/maxilirator/qlib_ext_se.git@main`, which builds this
same wheel. The three-tier design documented in `README.md:29-30` degrades to two tiers in
production, and the tier that disappears is the one designed to survive an outage of the
others. The defect is invisible to CI and to local development because both use
`pip install -e .`, where the source tree supplies the file.

**Failure scenario:** `pandas-market-calendars` is unavailable, incompatible after a
transitive upgrade, or raises on a requested range. On a developer machine the embedded
snapshot answers. In the production image the exception propagates out of
`build_xsto_trading_days` into the caller's data-preparation path and the job dies.

**Cross-repository reach today: none — and the reason is narrow.** `register()` does *not*
sit on this path: with every calendar tier and all networking sabotaged, `register()` still
completes (E-20), because the only calendar symbol it touches is the hardcoded
`se_trading_hours()`. And `qlib-trading` at `16425ce` imports no submodule of this package
and calls nothing but `register()` (E-19). So the defect is shipped in every consumer image
and is currently unreachable from consumer code — **contained by non-use, not by design**.
The first consumer line that follows `README.md:29-30` and calls `build_xsto_trading_days`
or `is_trading_day` activates it. This is a reason to fix it cheaply now, not a reason to
downgrade it. See [02 §5.4](02-cross-repository-interfaces.md).

**Remediation:** add `[tool.setuptools.package-data] "qlib_ext_se" = ["data/*.csv"]`, then
assert the file's presence in a packaging test (see F-11).

---

## P1

### F-03 — Calendar cache is written inside the installation directory

**Location:** `calendar.py:13,19-20,113,126,135`

`_CACHE_DIR = os.path.join(os.path.dirname(__file__), "_cache")` — the package caches into
itself. `build_xsto_trading_days` calls `_ensure_cache_dir()` unconditionally at line 113,
before any tier is attempted.

**Evidence (E-11).** With the installed package directory made read-only, the call raises a
`PermissionError` — at one of **two distinct sites**, depending on whether `_cache/` already
exists. Round 2 reproduced both (E-22):

| Precondition | Where it raises | Message |
|---|---|---|
| `_cache/` absent | `_ensure_cache_dir()` (`calendar.py:19-20`), *before any tier runs* | `Permission denied: '…/site-packages/qlib_ext_se/_cache'` |
| `_cache/` present but read-only | the cache write (`calendar.py:126`/`135`), *after* the tier has already produced the answer | `Permission denied: '…/site-packages/qlib_ext_se/_cache/xsto_2025-06-18_2025-06-24.csv'` |

The distinction matters for remediation, not for severity: in the first case no tier is ever
attempted, and in the second a correct result is computed and then discarded by an
unrecoverable write. **Either way the caller gets an exception and no calendar**, and no
fallback tier can help — the failure is in the cache layer that wraps all three.

**Failure scenario:** any hardened container (read-only root filesystem), any non-root
runtime user against a root-owned `site-packages`, or any shared/multi-tenant install. The
package is unusable, and the error surfaces as a permission problem rather than a
configuration one.

**Cross-repository reach today: none.** Same containment as F-02 — the write happens inside
`build_xsto_trading_days`, which `register()` never calls (E-20) and the consumer never
calls (E-19). See [02 §5.4](02-cross-repository-interfaces.md).

**Remediation:** resolve the cache to a user/state directory (`XDG_CACHE_HOME`,
`~/.cache/qlib-ext-se`) with an environment override, and make cache-write failure
non-fatal — a cache miss should degrade to recomputation, never to an exception.

---

### F-04 — pyqlib exact-pin is bypassed on arm64 images; `register()` fails at runtime

**Location:** `compat.py:7,22-27`; consumer `docker/Dockerfile.gpu.arm:57-60`

`SUPPORTED_PYQLIB_VERSIONS = ("0.9.7",)` and the gate raises for anything else. The
consumer's arm64 image installs `pyqlib==0.9.3`, then installs this package with
`--no-deps`, which suppresses the conflicting exact-pin at build time.

**Evidence (E-12):** the consumer's Dockerfile, including its own comment acknowledging the
workaround. `Dockerfile.gpu`, `.gpu.lite`, `.app-gpu-wheel`, `.app-gpu-wheel-cupybase`
default `aarch64|arm64` to `0.9.3` and fall back to it if the requested version is
unavailable.

**A second, subtler mechanism in `docker/Dockerfile.gpu` (E-19):** the pin is satisfied and
then invalidated by a later layer. Line 62 installs this package *with* deps, correctly
pulling `pyqlib==0.9.7`; lines 68-78 then install pyqlib again from an arch switch
(`x86_64→0.9.7`, `aarch64|arm64→0.9.3`, `*→0.9.6`), overwriting it; line 81 reinstalls this
package with `--no-deps`, so pip never re-checks. On x86_64 the arch default happens to match
the pin, so the image is consistent **by coincidence**. Any other architecture, or any
`--build-arg QLIB_VERSION=<other>`, ends with a rejected pyqlib and a silent build. See
[02 §C-5](02-cross-repository-interfaces.md).

**Evidence (E-13):** the gate's behaviour across versions —

```
pyqlib 0.9.3: RAISED RuntimeError: qlib-ext-se supports pyqlib versions ('0.9.7',), found 0.9.3.
pyqlib 0.9.6: RAISED RuntimeError: …
pyqlib 0.9.8: RAISED RuntimeError: …
pyqlib 0.9.7: register() OK
```

(pyqlib 0.9.3 publishes only cp37m/cp38 wheels and cannot be installed on 3.12, so the gate
was exercised directly against a stubbed `qlib.__version__` rather than a 0.9.3 install.
The gate is a string comparison against a one-element tuple; the mechanism is fully
determined by `compat.py:22-27`.)

**Failure scenario:** the arm64 image builds green and ships. At runtime the first
`register()` — which every consumer entry point calls — raises `RuntimeError`, and the job
fails at startup. The failure is total, not degraded, and it is architecture-dependent, so
it will not reproduce on the x86 machine where it is investigated.

**Remediation is a cross-repository decision, not a local one.** Either widen the gate to a
tested range and validate the patch points against each supported pyqlib, or drop arm64
support explicitly. Silently relaxing the gate is the wrong fix: the pin exists because the
package patches pyqlib internals, and those internals are not covered by any compatibility
promise. This finding should be worked jointly with the `qlib-trading` baseline.

---

### F-05 — `requires-python` has no upper bound

**Location:** `pyproject.toml:10`

`requires-python = ">=3.9"` advertises support for interpreters on which the package's own
mandatory dependency cannot be installed. `pyqlib==0.9.7` publishes wheels for cp38–cp312
and **no sdist**, so there is no build-from-source path either.

**Evidence (E-04):** on Python 3.13, resolution fails —

```
hint: You require CPython 3.13 (`cp313`), but we only found wheels for
`pyqlib` (v0.9.7) with the following Python ABI tags: `cp38`, `cp39`, `cp310`, `cp311`, `cp312`
```

**Failure scenario:** a consumer on a current interpreter follows the metadata, and gets a
resolver error that names `pyqlib`, not this package — so the diagnosis lands in the wrong
repository. This is precisely the confusion that produced the misdiagnosis noted in the
[README](README.md#two-claims-this-baseline-deliberately-does-not-make).

**Remediation:** `requires-python = ">=3.9,<3.13"`, matching the dependency's real support
window. Cheap, and it converts a confusing downstream error into a clear one.

---

### F-06 — The container "smoke test" runs zero tests

**Location:** `Dockerfile:5-6,12-13`

`COPY pyproject.toml README.md /app/` and `COPY src /app/src` — `tests/` is never copied.
`CMD ["pytest", "-q"]`, commented "Smoke test: calendar-only unit tests", therefore collects
nothing.

**Evidence (E-17):** reproducing the image's exact file set and command locally —

```
--- CMD ["pytest","-q"] ---
(no output)
EXIT CODE: 5
```

Exit 5 is pytest's "no tests collected".

**Failure scenario:** a CI or operator check that runs this image and treats it as a smoke
test gets either a false negative (if only stdout is read — it is empty, resembling
success) or an unexplained non-zero exit. Either way the image validates nothing.

**Remediation:** `COPY tests /app/tests`, or remove the `CMD` and the "smoke test" comment
so the image does not claim a guarantee it cannot provide.

---

### F-07 — XSTO early-close days are not modelled

**Location:** `calendar.py:157-159`; `region.py:38-44,54-65`

`se_trading_hours()` returns the constant `("09:00:00", "17:30:00")`, and the patched
`get_min_cal` builds the minute grid from it — so every session is 510 one-minute bars.

**Evidence (E-09):** XSTO scheduled 4 early closes in 2025, each closing at 13:00:

| Date | Open | Close |
|---|---|---|
| 2025-04-17 | 09:00 | 13:00 |
| 2025-04-30 | 09:00 | 13:00 |
| 2025-05-28 | 09:00 | 13:00 |
| 2025-10-31 | 09:00 | 13:00 |

**Evidence (E-10):** the registered calendar yields 510 bars for every day; the true count
on those dates is 240.

**Failure scenario:** any minute-frequency use — intraday features, minute backtests,
execution simulation — receives 270 phantom bars on those dates. Downstream this is not an
error but *silently wrong data*: fabricated post-close intervals that will be filled,
interpolated, or treated as no-trade, biasing intraday statistics and any execution model
calibrated on them.

**Current exposure is low and conditional.** The consumer's manifests are daily-frequency,
and no minute path was found in its code. This is latent, not active — which is why it is
P1 and not P0. It becomes P0 the day intraday work starts.

**Remediation:** derive session hours per date from the exchange schedule rather than a
constant; `pandas-market-calendars` already returns `market_open`/`market_close` per
session, so the data is available at the point where tier 2 is read. Until then, document
the daily-only constraint prominently.

---

### F-08 — `qlib-ext-se` is unpublished; the consumer's constraint breaks on any version bump

**Location:** consumer `pyproject.toml:14`

**Evidence (E-14):** neither `qlib-ext-se` nor `qlib_ext_se` exists on PyPI — both return
HTTP 404. The consumer nonetheless declares `"qlib-ext-se>=0.1.0"` as a runtime dependency
and, in its GPU Dockerfiles, installs the full dependency list with pip after a git install
of this package.

Verified pip behaviour with 0.1.0 already installed:

```
pip install "qlib-ext-se>=0.1.0"   → Requirement already satisfied   (index never queried)
pip install "qlib-ext-se>=0.2.0"   → ERROR: Could not find a version that satisfies the
                                     requirement qlib-ext-se>=0.2.0 (from versions: none)
```

**Failure scenario:** the build works today only because the constraint floor happens to
equal the installed version. The moment this package's version is raised — the ordinary
consequence of shipping any fix in this document — and the consumer's floor is raised with
it, the consumer's image build fails at the dependency-install step with a 404-shaped
resolver error. **This finding therefore gates the entire stabilization sequence**: the
release mechanism must be settled before any versioned fix is shipped.

**Remediation:** choose one and make it explicit — publish to an index the consumer's
builds can reach, or replace the consumer's PyPI-style constraint with a direct reference
(`qlib-ext-se @ git+https://…@<tag>`). Half-measures leave the consumer's build depending
on install ordering.

---

### F-09 — Consumer images install from the moving `@main` ref

**Location:** consumer `docker/Dockerfile.gpu:62,81`, `Dockerfile.gpu.arm:60`,
`Dockerfile.gpu.lite:42`, `Dockerfile.oracle-continuation-cloud:36` (all hardcoded `@main`),
plus `Dockerfile.app-gpu-wheel:60`, `Dockerfile.app-gpu-wheel-cupybase:42` and
`Dockerfile.runpod-retune:62` (`ARG QLIB_EXT_SE_REF=main` — overridable, unpinned by default)

```dockerfile
RUN pip install --no-cache-dir "git+https://github.com/maxilirator/qlib_ext_se.git@main#egg=qlib_ext_se"
```

`Dockerfile.gpu:61` carries the comment "For full reproducibility, replace @main with a tag
or commit SHA, e.g. @v0.1.0 or @<COMMIT_SHA>" — the risk is documented and unaddressed.

**Failure scenario:** any commit to this repository's default branch silently changes the
next consumer image build. Neither repository has a lock or constraints file (verified at
`16425ce` — E-19), there is no tag, and there is no review gate between the repositories, so
a change here can reach a consumer image without any consumer change. Two builds of the same
consumer commit can produce different images — which also means a consumer failure cannot be
reliably reproduced from its own git history, and no completed research artifact can be
attributed to a provider revision (see [02 §5.6](02-cross-repository-interfaces.md)).

**Remediation:** tag releases here and pin the consumer to tags or SHAs. Depends on F-08.
Pinning is the consumer's edit; having something to pin to is this repository's.

---

## P2

### F-10 — Divergent duplicate `normalize_symbol`; `.XSTO` suffix mishandled

**Location:** `defaults.py:8-20`; consumer `src/q_train/data/eodhd_utils.py:24-36`

`INSTRUCTIONS.md:21` presents symbol normalization as something "provided in this
extension". The consumer implements its own instead, with incompatible semantics (E-16):

| Input | `qlib_ext_se` | `qlib-trading` |
|---|---|---|
| `'ERIC-B.ST'` | `'ERICB.ST'` | `'eric-b'` |
| `'eric b'` | `'ERICB.ST'` | `'eric b'` |
| `'VOLV-B'` | `'VOLVB.ST'` | `'volv-b'` |
| `'ABB.XSTO'` | `'ABB.XSTO.ST'` | `'abb'` |
| `'  Atco A .ST '` | `'ATCOA.ST'` | `'atco a '` |

They disagree on case, suffix, and separator handling. Independently, the extension's
implementation only strips a `.ST` suffix, so `'ABB.XSTO'` becomes the double-suffixed
`'ABB.XSTO.ST'` — wrong on its own terms, not merely different.

`normalize_symbol` has **no test** (`defaults.py:13-20` is 0% covered, E-15).

**Failure scenario:** currently inert — the consumer never imports it (verified exhaustively
at `16425ce`: no `from qlib_ext_se import …` and no submodule import anywhere in the consumer
tree, E-19). The trap is that a future consumer author follows `INSTRUCTIONS.md`, adopts the
extension's helper for one code path, and silently produces instrument identifiers that do
not join against the existing ones — the consumer's own `normalize_symbols` is already wired
into `QlibDataConnector.normalize_instruments`
(`src/q_train/data/qlib_data_connector.py:217-218`). The resulting mismatch surfaces as
missing data, not as an error.

**Remediation:** decide ownership. Either delete it from this package and correct
`INSTRUCTIONS.md`, or make it canonical, fix the suffix handling, test it, and migrate the
consumer. Do not leave two.

---

### F-11 — Both failure-path calendar tiers and both patched functions are untested

**Location:** `tests/`; measured in E-15

62% statement coverage overall, concentrated in the wrong places:

- `calendar.py:52-87, 97-103` — the entire EODHD tier: 0%.
- `calendar.py:137-149` — the embedded-CSV fallback tier: 0%.
- `region.py:55-76` — the bodies of `get_min_cal_extended` and
  `time_to_day_index_extended`: 0%. The tests install these functions and never call them.
- `defaults.py:13-20` — `normalize_symbol`: 0%.

**Failure scenario:** this is the reason F-02 and F-07 could ship undetected. The suite
verifies that patching *happened*, not that the patched code is *correct*, and it never
exercises a degraded path. Any regression in fallback behaviour is invisible to CI.

**Remediation, in value order:** (1) a packaging test asserting the fallback CSV is present
in a built wheel — this alone would have caught F-02; (2) tier-3 test with tier 2 forced to
fail; (3) tier-1 test with a stubbed HTTP response covering both documented response
shapes; (4) direct assertions on the patched functions' outputs, including bar counts.

---

### F-12 — Cache key produces one file per queried date, with no invalidation or provenance

**Location:** `calendar.py:23-24,114-116,126,135`

The cache file name is derived from the `(start, end)` pair, so
`is_trading_day(d)` → `build_xsto_trading_days(d, d)` creates a distinct file per date.
Observed in E-11: a 4-date test run left exactly four files —
`xsto_2025-06-18_2025-06-18.csv`, `…-06-19…`, `…-06-20…`, `…-06-23…`.

Three compounding problems: unbounded file growth under per-date querying; **no expiry or
invalidation** — a cached range is returned forever, so a corrected exchange schedule never
propagates; and **no provenance** — a cache entry does not record which tier produced it, so
a file synthesized by tier 1 is indistinguishable from an authoritative tier-2 answer.

**Failure scenario:** a service calling `is_trading_day` daily accumulates one file per
day inside `site-packages` indefinitely; and a calendar error cached during an EODHD
degradation persists silently after EODHD recovers.

**Remediation:** cache on a coarse granularity (per year), record source and fetch time in
the file, and add a TTL or explicit invalidation. Combine with F-03's relocation.

---

### F-13 — Calendar tiers 1 and 2 compute sessions on different bases; tier-1 errors are swallowed

**Location:** `calendar.py:41-43,90-103` (tier 1) vs `27-33` (tier 2); `85-87`

Tier 1 does not fetch sessions — it **synthesizes** them as `pd.bdate_range(freq="C")`
minus an EODHD holiday list. Tier 2 reads the maintained XSTO exchange schedule. Weekday
arithmetic cannot represent an unscheduled closure, a special session, or an exchange-level
schedule change not expressed as a holiday record, so the two tiers can legitimately
disagree — and tier 1 is *preferred* whenever a key is present.

**Evidence (E-23), measured in round 2 rather than argued.** Tier 1 was exercised
end-to-end with a stubbed holiday response (no network call, no credential used):

| Tier-1 holiday response | Sessions returned for 2025 | Divergence from XSTO (249) |
|---|---|---|
| correct for the window (Midsummer's Eve stubbed in) | matches tier 2 exactly on that window | none |
| **empty — the shape a degraded or schema-changed API returns** | **261** | **12 fabricated sessions**, including 2025-01-01, 2025-01-06, 2025-04-18, 2025-04-21, 2025-05-01, 2025-05-29 |

So the mechanism works when the feed is right, and silently fabricates New Year's Day, Good
Friday, Easter Monday, May Day and Ascension as trading days when it is not. The result is
then cached (F-12) and served indefinitely.

`_fetch_holidays_eodhd` catches every exception, logs at `debug`, and returns `None`
(`calendar.py:85-87`); individual malformed date entries are also silently skipped
(lines 69-72, 80-83). A partial or empty holiday response therefore degrades to "no
holidays", producing a calendar that treats every weekday as a trading day, with no signal
above debug level.

**Failure scenario:** with a key configured, an EODHD outage or schema change yields
Mon–Fri-everything for the requested range; that result is cached (F-12) and returned
thereafter. Public holidays become trading days, and the only trace is a debug log line.

Note the interaction with F-01: the token in `pyproject.toml` is *not* on the lookup path,
so this repository's committed credential does not currently enable tier 1 anywhere.

**Remediation:** log tier-1 failures at warning or above; validate the response (a non-empty
holiday set is expected for any multi-month Swedish range); record the tier in the cache;
and consider reversing the preference so the maintained exchange schedule is authoritative
and EODHD is the cross-check.

---

### F-14 — No lock file; direct dependencies are floor-pinned only

**Location:** `pyproject.toml:19-26`

`pandas>=2.0`, `pandas-market-calendars>=4.3.2`, `requests>=2.31`, `python-dateutil`, `pytz`
— all unbounded above; the last two have no constraint at all. There is no lock file, and CI
resolves fresh on every run.

Installing this 229-statement package currently pulls **204 distributions, ~942 MB** (E-02),
because pyqlib transitively brings mlflow, scikit-learn, and lightgbm. That is a very large
unpinned surface for a package whose own correctness depends on the internal layout of one
of those dependencies.

**Failure scenario:** a pandas or `pandas-market-calendars` major release changes behaviour
in `_generate_with_pmc` or the `DatetimeIndex` handling, and CI turns red — or worse, stays
green while a production image built the same day gets a different resolution. The
green-CI-and-broken-image split is the real risk here, given F-09.

**Remediation:** add upper bounds on the direct dependencies with observed compatibility, and
commit a lock file for CI and image builds. Resolved versions at the time of assessment,
recorded in E-02 as a starting point: pyqlib 0.9.7, pandas 2.3.3, numpy 2.5.2,
python-dateutil 2.9.0.post0, pytz 2026.3.post1, requests 2.34.2.

---

### F-15 — CI does not build a wheel, lint, type-check, or test a matrix

**Location:** `.github/workflows/ci.yml`

One job: checkout, Python 3.12, `pip install -e .`, `pytest -q`. Recent runs are green
(E-01), and that green is honest as far as it goes — but it covers a single interpreter and
a single install mode.

Not covered: wheel build and content verification (F-02 is invisible to CI **because** CI
uses `-e .`); linting or formatting — no config for any linter exists in the tree;
type-checking — no annotations config, no `py.typed`; an interpreter matrix across the
declared 3.9–3.12 range; the container image (F-06); and any dependency audit.

**Failure scenario:** a green badge that does not distinguish "the package works" from "the
package imports on one machine". F-02, F-06, and F-17 are all CI-invisible today.

**Remediation:** add a `python -m build` + wheel-content assertion step (highest value per
line of YAML), then a 3.9/3.12 matrix, then lint.

---

### F-16 — `unregister()` removes state it may not own

**Location:** `region.py:118-132`

`unregister()` deletes `qlib.constant.REG_SE` whenever its value equals `"se"`, and pops
`_default_region_config["se"]`, regardless of who installed them. `register()` is correctly
ownership-aware — it only writes when the key is absent (`region.py:17,26`) — so the pair is
asymmetric: `register()` will not overwrite a pre-existing entry, but `unregister()` will
happily delete it.

The function-restore path is correct: `_ORIGINALS` is populated once, and E-10 confirms
`get_min_cal` is restored to the identical original object after a register/unregister
cycle.

**Failure scenario:** two components in one process both arrange SE support — this package
and, say, a future consumer-side patch. The first `unregister()` tears down the shared
registration, and the surviving component silently loses its region. `unregister()` has zero
consumer call sites today, so this is latent.

**Remediation:** record in `_ORIGINALS` whether `register()` actually created each entry,
and only remove what was created.

---

## P3

### F-17 — The TOML credential path is silently inert on Python 3.9/3.10

**Location:** `config.py:6-9,24-28`

`tomllib` is stdlib only from 3.11. The import is guarded, and `_read_toml` returns `{}`
when `tomllib` is `None` — so on 3.9 and 3.10, both inside the declared `>=3.9` support
range, `get_eodhd_api_key()` returns `None` for a perfectly valid config file, with no
warning.

**Evidence (E-18):** same config file, same code path, both interpreter conditions —

```
3.11+ (tomllib present): SAMPLE-KEY
3.9/3.10 (tomllib None): None
```

**Failure scenario:** an operator on 3.10 follows `README.md:24-27`, writes the TOML file,
and gets calendar tier 2 with no indication that their credential was ignored. Silent
degradation of a documented configuration mechanism.

**Remediation:** either add `tomli` as a conditional dependency
(`tomli; python_version < "3.11"`), or raise `requires-python` to `>=3.11` and delete the
guard. The latter is simpler and consistent with F-05.

---

### F-18 — README understates the embedded calendar's coverage

**Location:** `README.md:30`

"As a last resort, falls back to an embedded CSV snapshot of trading days for a small
audited window."

The snapshot is not small: 9,041 sessions spanning 2000-01-03 → 2035-12-28 (E-08). More
importantly, it is **exactly correct** — a full set comparison against
`pandas-market-calendars` XSTO over its whole range shows zero divergence in either
direction. This is the strongest asset in the repository, described in a way that
discourages relying on it.

**Failure scenario:** documentation-driven; an operator reading this sentence reasonably
concludes the fallback is a stub and designs around it. Combined with F-02, the actual
situation is inverted: the fallback is excellent and it is missing from production installs.

**Remediation:** state the real range, the session count, and the verification date; add the
parity check to CI so the claim stays true.

---

### F-19 — Repository hygiene: no CHANGELOG, CODEOWNERS, SECURITY.md, or `py.typed`; version dual-sourced

**Location:** repository root; `pyproject.toml:7`, `__init__.py:10`

Absent from the tree: `CHANGELOG.md`, `CODEOWNERS`, `SECURITY.md`, `CONTRIBUTING.md`,
`py.typed`, `MANIFEST.in`, any lint/format config, and any `AGENTS.md`/`CLAUDE.md`.
`authors = [{ name = "Your Team" }]` (`pyproject.toml:12`) is an unedited template value.

The version is declared in two places — `pyproject.toml:7` and `__init__.py:10` — with no
mechanism keeping them equal. Both currently read `0.1.0`.

**Failure scenario:** no security contact for reporting something like F-01; no changelog,
so a consumer pinned to `@main` (F-09) cannot tell what changed; version drift makes the
runtime `__version__` an unreliable diagnostic. All low-impact individually, all cheap.

**Remediation:** single-source the version (`dynamic = ["version"]` reading `__init__.py`),
add `SECURITY.md` and `CODEOWNERS`, set a real `authors` value, and add `py.typed` if the
annotations are intended to be public.

---

## Verified-sound behaviours

Recorded deliberately: these were tested and found correct, and should not be disturbed by
remediation.

| Behaviour | Evidence |
|---|---|
| Embedded calendar matches XSTO exactly — 9,041 sessions, 2000-01-03→2035-12-28, zero divergence both ways | E-08 |
| `register()` is idempotent; a second call does not grow `_default_region_config` | E-10 |
| `unregister()` restores `get_min_cal` to the identical original object | E-10 |
| Non-`se` regions are unaffected — `cn` minute calendar still 240 bars after registration | E-10 |
| The pyqlib version gate correctly accepts only 0.9.7 and produces an actionable message | E-13 |
| Region defaults install exactly as documented (`deal_price='adjusted_close'`, `trade_unit=1`) | E-10 |
| The test suite passes on a supported interpreter with declared dependencies present | E-03 |
