# Golden-Test Verification Method (shared across all Mu→Python migrations)

This is the **shared verification contract** for every package migrated from Mu to
Python via golden tests. Each package has its own inventory doc (e.g.
`session_manager/COVERAGE.md`) that plugs into the method defined here. Design rationale:
`docs/superpowers/specs/2026-07-21-mu-to-python-golden-tests-design.md`.

The migration uses baseline behaviour and appearance from the Mu implementation. Refactored code will be compared with the baseline tests.

```
setup:   [Mu package] --capture--> golden (committed)     ┐ actual == golden → PASS
         [Mu package] --run------> actual                 ┘ (proves determinism only)

loop:    [Mu package] --capture--> golden (already committed)
         [Python port]--run------> actual   actual == golden ?  ← the real migration gate
```

A **passing scenario before a port exists means only that the Mu capture is reproducible
(Mu == Mu)** — it does not verify any migration. The real test is when the Python port is
toggled in (see [Mu/Python implementation toggle](#mupython-implementation-toggle))
and the same scenarios run against it.

---

## Mu/Python implementation toggle

Both the Mu and Python sources for a package can live in the same build. RV normally loads **Mu first** when a `.mu` module exists; Python is only a fallback. For migration we need to run a **Python** mode against Mu-captured goldens without removing the Mu sources from the tree.

### Environment variables

`<modeName>` is the RV mode name from `PACKAGE` / `rvload2` (extension stripped),
e.g. `session_manager`, `Stack_edit_mode`.

| Variable | Example | Effect |
|---|---|---|
| `RV_MODE_IMPL_<modeName>` | `RV_MODE_IMPL_session_manager=python` | Per-mode: `python` skips Mu and loads `<modeName>.py`; `mu` forces Mu-first (default behavior). |
| `RV_PREFER_PYTHON_MODES` | `RV_PREFER_PYTHON_MODES=session_manager,pyhello` | Comma-separated list of modes to load from Python when both exist. |

Precedence: per-mode `RV_MODE_IMPL_*` → `RV_PREFER_PYTHON_MODES` → default Mu-first.

### Harness

```bash
# Mu (default): capture goldens, prove Mu determinism, re-baseline
python3 src/test/golden/harness/run_scenario.py \
    --scenario src/test/golden/session_manager/scenarios/tree_readonly.py \
    --out /tmp/tree_readonly --impl mu

# Python: migration loop / port verification against committed goldens
python3 src/test/golden/harness/run_scenario.py \
    --scenario src/test/golden/session_manager/scenarios/tree_readonly.py \
    --out /tmp/tree_readonly --impl python
```

### Limits

- Requires `<modeName>.py` with a `createMode()` entry point on the Python path.

---

## The five gates

Every Mu→Python package migration must pass these **five mandatory gates**, in order.
Package orchestrators (`run_migration_loop.sh` / `run_migration_loop_mac.sh`) run them
sequentially; on any failure the script exits immediately.

| Gate | Name | Command (orchestrator sets) | Pass criteria |
|------|------|-----------------------------|---------------|
| **0** | Runtime clean | `GATE=runtime IMPL=python` | Every scenario: no tracebacks, exceptions, or `runtime.eval` errors in `$out/rv.log` or `traceback.txt` (`harness/runtime_log_check.py`). Enforced on every `run_scenario.py` call, not only in this gate. |
| **1** | Behavioral | `GATE=behavioral IMPL=python` | Every scenario: normalized `session.rv` matches committed golden (node graph, properties, connections). |
| **2** | Pixel | `GATE=pixel IMPL=python` | Every golden PNG: `rmsImageDiff -cmp -dmax 0` (see [Determinism requirements (gate 2)](#determinism-requirements-gate-2)). |
| **3** | Default launch | `GATE=default` | Every scenario: behavioral match with `--impl default` (no `RV_MODE_IMPL_*`; RV picks its shipped default). |
| **4** | Mu baseline integrity | `GATE=both IMPL=mu` | Every scenario: Mu implementation still matches committed goldens (harness and baselines sound). |

Gates **1** and **2** are complementary: behavioral catches logic the graph can see; pixel
catches layout/rendering it cannot. Some inventory items apply to one gate only (noted in
each package's `COVERAGE.md`).

### Gate 0 — Runtime clean

`run_scenario.py` captures RV stdout/stderr to `$out/rv.log`. Exit code **5** if the log
or `traceback.txt` contains runtime failures in the package under test. Event-handler
exceptions (e.g. during widget clicks) do not fail the scenario script itself — this gate
catches them.

### Gate 1 — Behavioral

After a scripted scenario, `compare.py` diffs normalized GTO from `saveSession(sparse=False)`
against the committed golden.

### Gate 2 — Pixel

After a scripted scenario, panel/viewport PNGs are compared at `-dmax 0` under the pinned
headless path (Xvfb + software Mesa on Linux; real display + `golden-mac/` on macOS).

### Gate 3 — Default launch

Same behavioral check as gate 1, but scenarios run with `--impl default` so RV's normal
mode-selection path is exercised (not an explicit `RV_MODE_IMPL_*` override).

### Gate 4 — Mu baseline integrity

Full scenario pass with `IMPL=mu`. Confirms committed goldens and harness still match Mu;
never hand-edit `golden/` or `golden-mac/`.

**Platform baselines:** Mac output compares to `golden-mac/` only; Linux to `golden/` only
— never cross-compare ([Mac-native capture](#mac-native-capture)).

**Conditional steps** (not gates): after gates 0–2 pass, the orchestrator may run [GUI
sanity](#gui-sanity-real-display) and the [code review agent](#code-review-agent). These
are required before calling migration done but are not numbered gates.

---

Used by every package inventory. **A ✅ means the behavior is pinned by a committed golden
(the Mu ground truth is recorded) — NOT that it has been verified in the Python port.**

- ✅ **covered** — a committed scenario exercises and pins this behavior.
- 🟡 **partial** — touched by a scenario but not fully pinned (e.g. rendered but not
  interacted with).
- ⬜ **todo** — no scenario yet; listed in the package's scenario backlog.

Behaviors with no deterministic graph/pixel outcome and no command equivalent (modal UI,
settings persistence, async previews, "event was sent") are **dropped** — removed from the
inventory rather than tracked — and noted in a short "Dropped" section per package.

---

## The harness

Reusable across all packages; lives in `src/test/golden/harness/`.

| File | Role |
|---|---|
| `run_scenario.py` | Launches RV headless (Xvfb + software Mesa), runs an in-process scenario, collects artifacts into an out dir. Captures RV log to `$out/rv.log`; fails on runtime errors unless `--allow-runtime-errors`. Pass `--impl mu\|python` and optional `--mode` to select implementations. When the rv-packages directory name differs from the mode name, pass `--package <dir>` (e.g. `--mode layer_select_mode --package layer_select`). Runs `golden_bootstrap.py` before each scenario. |
| `runtime_log_check.py` | Scans `rv.log` / `traceback.txt` for runtime failures; used by `run_scenario.py` and `GATE=runtime`. Allowlist for infra-only noise: `runtime_error_allowlist.txt`. |
| `golden_bootstrap.py` | In-RV pre-scenario hook: activates `source_setup` when `GOLDEN_SOURCE_SETUP=1` (set automatically for `tree_readonly.py`). |
| `compare.py` | Normalized GTO diff + `rmsImageDiff` pixel compare (gates 1 and 2). Exit 0 = PASS. |

### Package runners (`session_manager`)

| File | Role |
|---|---|
| `session_manager/run_all_goldens.sh` | Linux scenario runner — used by the orchestrator for [the five gates](#the-five-gates); `compare.py` against `golden/`. |
| `session_manager/run_gui_sanity_gate.sh` | Conditional real-display step; see [GUI sanity](#gui-sanity-real-display). |
| `session_manager/run_all_goldens_mac.sh` | macOS scenario runner — same role, compared against `golden-mac/` ([Mac-native capture](#mac-native-capture)). |
| `session_manager/capture_golden.sh` | Capture Mu baselines into `golden/<id>/` on Linux (`--impl mu` via `run_scenario.py`, under Xvfb). |
| `session_manager/capture_golden_mac.sh` | Capture Mu baselines into `golden-mac/<id>/` on macOS (real display). Captures each scenario twice and refuses to commit unless both captures are byte-identical. |
| `session_manager/fixtures/run_mp4_integration.sh` | Optional integration only (`sm_mp4_all`); not part of `run_all_goldens.sh`. |

```bash
# Migration loop, Linux (Python port must pass all committed goldens):
src/test/golden/session_manager/run_all_goldens.sh

# Migration loop, macOS (against the separate Mac-native baselines):
src/test/golden/session_manager/run_all_goldens_mac.sh

# Re-capture Mu baselines after intentional behavior change:
src/test/golden/session_manager/capture_golden.sh [scenario_id ...]        # Linux
src/test/golden/session_manager/capture_golden_mac.sh [scenario_id ...]    # macOS
```

Skipped by both `run_all_goldens.sh` and `run_all_goldens_mac.sh` (no golden baseline by
design): `sm_mp4_all`, `sm_reopen_after_hide`, `sm_toggle_diag`, `sm_thumb_diag`,
`sm_thumb_diag2`.

### Layout per package

```
src/test/golden/
  VERIFICATION.md            # this file (shared method)
  harness/                   # shared run_scenario.py + compare.py
  <package>/
    COVERAGE.md              # package-specific behavior inventory + file list
    scenarios/<id>.py        # in-RV scenarios (command-API driven; QTest for DnD)
    run_migration_loop.sh    # full migration loop orchestrator (Linux)
    run_migration_loop_mac.sh
    run_all_goldens.sh       # scenario runners (orchestrator only; debug individually)
    run_all_goldens_mac.sh
    run_gui_sanity_gate.sh   # conditional sanity step (orchestrator calls this)
    capture_golden.sh        # Mu baseline capture (Linux)
    capture_golden_mac.sh    # Mu baseline capture (macOS)
    golden/<id>/             # committed Linux baselines: session.rv (+ *.png)
    golden-mac/<id>/         # committed macOS baselines (separate pixel space)
```

Package-specific harness notes (fixtures, mode/package name mismatches, headless
caveats) belong in `COVERAGE.md`, not a separate doc — unless the package needs a
one-line pointer file, keep everything in COVERAGE.

### Headless operational rules

- Launch under `xvfb-run` with `LIBGL_ALWAYS_SOFTWARE=1`. **`QT_QPA_PLATFORM=offscreen`
  segfaults RV** (its offscreen GL plugin needs GLX). Software Mesa under Xvfb is
  deterministic given a pinned Mesa version.
- **RV redirects stdout to its own log** (`~/.local/share/rv.bin/rv.bin.log`). Scenarios
  must write results to explicit files under `$GOLDEN_OUT`, not print them.
- **`close()` does not quit a windowless RV.** Every scenario ends by hard-exiting; the
  runner wraps scenarios so they always `os._exit`.
- `-pyeval` runs **before** the Qt event loop, so widgets don't paint on their own — pump
  the event loop (`QApplication.processEvents`) before `grab()`.
- **Immediate modes** (e.g. `source_setup`) load at `state-initialized` but start **inactive**
  in headless runs; the harness re-activates them via `golden_bootstrap.py` when needed.
  Set `GOLDEN_SOURCE_SETUP=1` to force color setup for all scenarios (default: off except
  `tree_readonly.py`, which pins movieproc `sRGB2linear=1`).
- Scenarios drive the package via the `rv.commands` API (deterministic, headless-safe).
  Drag-and-drop and other pointer interactions need synthetic Qt input events (`QTest`);
  schedule those scenarios last.

---

## Determinism requirements (gate 2)

A hard `-dmax 0` gate is only safe if capture is bit-reproducible.

| Source of nondeterminism | Fix |
|---|---|
| GPU/driver variance | Render through **software Mesa under Xvfb**, not the GPU; pin the Mesa version. |
| Async thumbnails/previews | Use media-free fixtures where possible; else quiesce on the relevant "available" event for every item before grabbing, **or** crop the nondeterministic region out of the PNG before diffing (`rmsImageDiff` has no ROI/mask). |
| Fonts / hinting | Pin a bundled font + fixed `fontconfig`; set a fixed `QT_FONT_DPI`. |
| HiDPI scaling | `QT_SCALE_FACTOR=1`, `QT_ENABLE_HIGHDPI_SCALING=0`, fixed widget size. |
| Animations / hover | Disable animations; command-API driving avoids stray focus/hover. |
| Xvfb / Mesa drift | Pin Xvfb screen geometry and Mesa version; capture goldens in the same container/path used to test. |

Gate at `-dmax 0` (exact); loosen `dmax` only if residual noise is *observed*, and always
log `-m` (max error) so drift surfaces. Never loosen `dmax` to paper over flakiness — a
flaky gate trains the AI loop to hack the oracle.

---

## GUI sanity (real display)

`run_all_goldens.sh` above is deterministic, but it pins exactly one rendering path: Xvfb +
software Mesa. A port can pass that gate while being visibly broken under a real
GPU/compositor/font stack — or, less obviously, the reverse: differ from Mu only because of
environment noise the headless path can't see. `<package>/run_gui_sanity_gate.sh` exists to
catch that class of regression by re-running the same scenarios against a real on-screen
display instead of Xvfb.

This is a **required step, not a smoke test — and deliberately not a numbered gate.** It runs
two independent checks per scenario:

- **Behavioral (node graph):** same as headless, always exact, HARD. A real-display run
  producing a different node graph than the pinned golden is exactly as serious as it is
  headlessly, and fails the script's exit code (the loop must iterate again).
- **Pixel (panel.png etc.):** no threshold, no verdict, via `compare.py --pixel-mode
  report`. Real GPU/font/compositor rendering is never byte-identical to a golden captured
  under Xvfb + software Mesa, so any fixed `dmax` is wrong in one of two directions: tight
  enough to catch real regressions and it fails permanently on rendering noise (training
  whoever/whatever runs the loop to ignore this gate as always-red, which is worse than not
  having it); loose enough to stay quiet on noise and it can silently swallow a real
  regression. Rather than guess a number, the gate prints quantitative info — RMS, the
  max-diff pixel location and its two values, and both PNG paths — and leaves the judgment to
  a **reviewer, human or AI**: does this look like ordinary rendering noise (anti-aliasing,
  font hinting, GPU vs. software raster) or a real behavioral/visual regression? If judged
  real, that's a failure for this iteration even though the script exited `0` — the AI
  running the loop is expected to open the flagged PNGs (its own image-reading tool, or by
  eye) and make that call itself, same as a human would eyeball a screenshot.

Missing artifacts are still a hard fail either way — whether a PNG was produced at all is
objective (a broken port that can't find the widget never writes the file), only its pixel
*content* is left to review.

`run_gui_sanity_gate.sh` prints a `NEEDS_AI_REVIEW:` line listing every scenario whose
behavioral gate passed but which has a pixel report attached, so the reviewer knows exactly
which scenarios to look at without re-reading the whole log.

The script's final phase re-runs scenarios with `--impl default` on a real display. See
[Gate 3](#gate-3--default-launch); the orchestrator runs the authoritative Gate 3 pass via
`run_all_goldens*`.

**Known bug, `sm_meridian_mp4_load` and `sm_media_add_sources` skipped:** both use
`addSources()` + `waitForProgressiveLoading()`, which hangs forever under a real display
(confirmed 2026-07-24 — native, not fixable from the Python/test side; neither Qt
event-pumping nor a forced synchronous repaint on the real GL widget advances it). Since this
script always runs `--no-xvfb`, both are in its `SKIP_IDS` until the underlying render/load
path is fixed.

---

## Mac-native capture

Unlike [GUI sanity](#gui-sanity-real-display) (real display, but judged against Linux
`golden/` baselines, so pixel is report-only), macOS migration uses a **separate committed
baseline tree** `golden-mac/`: Mac output is compared only against Mac-captured baselines via
`run_all_goldens_mac.sh` / `capture_golden_mac.sh`. It does not replace `golden/` — the two
pixel spaces are not comparable and are never diffed against each other.

**Why separate Mac baselines work** (verified empirically
2026-07-24 on one Mac dev machine, real logged-in display session, no Xvfb — macOS has
none):

- Two back-to-back captures of `tree_readonly` produced a byte-identical `session.rv` and a
  byte-identical `panel.png` (`rmsImageDiff -m` reported no diff). Real-display rendering
  *can* be bit-reproducible on a fixed machine/session, unlike the cross-machine/cross-GPU
  case the GUI sanity gate exists for.
- The *behavioral* graph captured on Mac matched the already-committed Linux `golden/`
  baseline exactly — the node graph is platform-independent, so in principle `golden-mac/`'s
  behavioral half is redundant with `golden/`'s. It's still captured and stored per-scenario
  in `golden-mac/` (not deduplicated against `golden/`) to keep each platform's baseline set
  self-contained per the [layout convention](#the-harness).
- *Pixel* is not platform-independent and cannot be pinned once for both: the same scenario's
  Mac capture came out at exactly 2x the Linux golden's raw pixel dimensions (Retina/HiDPI
  backing-scale-factor), before any content is even compared. `golden-mac/` pixel baselines
  are mandatory and separate.

**Determinism is not assumed globally — it's enforced per capture machine.**
`capture_golden_mac.sh` runs every scenario twice back-to-back and refuses to commit a
baseline unless both runs are byte-identical (session.rv via `diff`, every PNG via
`rmsImageDiff -m` showing no max-diff line). A scenario that fails this check is skipped
with an error, never committed with a caveat — same "never loosen the gate to paper over
flakiness" principle as everywhere else in this doc, applied automatically at capture time
instead of discovered later.

**Known limitation, not yet resolved:** everything above was verified using a real,
logged-in GUI/WindowServer session on one interactive dev Mac. A genuinely unattended,
no-monitor Mac (e.g. a CI runner nobody is logged into) is a materially different and
untested question — Qt/Cocoa apps generally require a WindowServer session to exist at all.
Before relying on this gate in an unattended CI environment, verify RV actually launches and
renders there first; don't assume the dev-machine result transfers.

**Known bug, `sm_meridian_mp4_load` and `sm_media_add_sources` skipped:** same real-display
`waitForProgressiveLoading()` hang as the GUI sanity gate above — both are in
`capture_golden_mac.sh`'s and `run_all_goldens_mac.sh`'s `SKIP_IDS` until fixed. All other 47
scenarios are captured and determinism-verified in `golden-mac/` as of 2026-07-24 (100% of
what's currently capturable given the two skips).

**Transient, not a structural bug: `sm_folder_sort` failed its determinism check once**
during the full-batch capture (a single pixel differed between the two runs — mid-gray value
shift at one coordinate, everything else identical). The scenario is command-API-driven with
no scripted hover/click, so the likely cause is incidental: this machine's real, shared mouse
cursor sitting somewhere different over RV's window between the two runs during a busy
capture batch — a risk specific to real-display capture on an otherwise-in-use dev machine
(Xvfb has no such shared cursor state). Re-run alone immediately after, with the machine
otherwise idle, it passed cleanly and is now committed. If this recurs, don't relax the
check — re-run in isolation first, since a busy machine is a more likely explanation than a
real scenario bug.

---

## Migration loop

The migration loop runs [the five gates](#the-five-gates) via each package's orchestrator.
Package inventories (`COVERAGE.md`) hold behavior lists, fixtures, and package-specific
debug hints only.

### Orchestrator script

Each package provides `run_migration_loop.sh` (Linux / `golden/`) and/or
`run_migration_loop_mac.sh` (macOS / `golden-mac/`). One invocation runs gates **0 → 4**
in order, then conditional GUI sanity and code-review steps if gates 0–2 passed.

Scenario iteration lives in `run_all_goldens*.sh`; gate sequencing lives in the
orchestrator. On any failure the script **exits immediately**. Fix the port, then run the
**same script again** — that is the loop.

```bash
# macOS (typical dev path when golden-mac/ exists):
cd src/test/golden/<package>
./run_migration_loop_mac.sh

# Linux (after capture_golden.sh):
./run_migration_loop.sh
```

Do **not** run `GATE=behavioral ./run_all_goldens*.sh` as the normal workflow — that is
for debugging a single failing scenario only.

Individual gate env vars (`GATE`, `IMPL`) are set by the orchestrator — do not override
when running the full loop. See [The five gates](#the-five-gates) for what each gate checks.

Orchestrator env vars (all packages):

| Variable | Default | Purpose |
|----------|---------|---------|
| `SKIP_SANITY` | `0` | `1` = skip GUI sanity step (local dev only) |
| `SKIP_REVIEW` | `0` | `1` = skip code-review reminder (local dev only) |
| `SKIP_PIXEL_GATE` | `0` | `1` = accept gate 2 failure and continue (package-specific; use sparingly) |

If gate 0, 1, or 2 fails, the orchestrator never reaches sanity, review, or gates 3–4.

The **agent** drives the loop: edit the Python port → `./run_migration_loop*.sh` → repeat
until exit 0 or **15 failed runs** ([allowed operations](#allowed-operations) §2).

Do **not**:

- Run gates or scenarios individually except when debugging one failure
- Use iteration counters or env vars (`ITERATION=`, etc.)
- Call migration done until the orchestrator exits 0 **and** sanity pixel review **and**
  code review (no blocking findings) are satisfied
- **Stop early because of a blocker** — see [When you hit a blocker](#when-you-hit-a-blocker-keep-going-until-unblocked) below

**Loop algorithm:**

```
attempts = 0
while attempts < 15:
    attempts += 1
    fix Python port under src/plugins/rv-packages/<package>/
    run: ./run_migration_loop_mac.sh   # or run_migration_loop.sh on Linux
    if exit 0:
        judge NEEDS_AI_REVIEW pixel reports (if any) — real regression → keep looping
        run code review agent — blocking findings → fix and keep looping
        if both satisfied → DONE
    else:
        read which GATE failed from script output
        diagnose (diag.txt under /tmp, compare.py on failing scenario)
        if root cause is still unclear → keep investigating; do not hand off yet
report failure after 15 attempts
```

#### When you hit a blocker — keep going until unblocked

A **blocker** is anything that prevents the next gate from passing even though the
immediate Python diff looks “done”: harness wiring, mode activation/registration, Mu helper
not loading, segfaults in a render path, optional-package preload under `-noPrefs`, stale
`rvpkg`/`rvload2`, missing fixtures, etc.

**Do not** treat a blocker as a reason to pause the loop, summarize, or ask the user
“what next?” unless you genuinely need a product decision or credentials you cannot infer
from the repo.

**Do** stay in the loop until the blocker is removed:

1. **Name the blocker precisely** — e.g. `LayerSelectRender` inactive (`isModeActive`
   false), not vague “pixel mismatch”.
2. **Debug in isolation** — one scenario, `diag.txt`, minimal repro, Mu vs Python, with/without
   harness flags; read RV stderr and mode-manager messages.
3. **Try the next fix** — PACKAGE/`rvload2`, preload, separate rvpkg, harness env, Mu bridge,
   alternate architecture; rebuild staged artifacts when needed.
4. **Re-run the orchestrator** after each meaningful change (`./run_migration_loop*.sh`, or
   the single failing gate/scenario while iterating).
5. **Repeat** until the gate passes or you hit the 15-run cap.

Stopping with “here’s the blocker” without exhausting reasonable fixes counts as an
**incomplete loop run**. The user expects the agent to **keep doing what it takes** to
unblock — same session, same task — not defer infrastructure work back to them.

Only escalate to the user when:

- You need an explicit product/architecture choice (e.g. modify a core cpp file)
- You need assets or credentials not in the repo
- 15 full loop attempts failed and you can document what was tried

### On failure — which gate?

| Script output | Typical cause |
|---------------|---------------|
| `GATE 0 FAILED` | Runtime error during scenario — tracebacks, `runtime.eval`, exceptions in `$out/rv.log` |
| `GATE 1 FAILED` | Wrong graph/properties — logic, property writes, mode lifecycle |
| `GATE 2 FAILED` | Visual regression — layout, GL render, widget state |
| `SANITY FAILED` | Real-display behavioral drift (same class as gate 1) |
| `NEEDS_AI_REVIEW` | Pixel diff on real display — inspect PNGs; see [GUI sanity](#gui-sanity-real-display) |
| `GATE 3 FAILED` | Broken default launch path — PACKAGE wiring, mode registration, preload |
| `GATE 4 FAILED` | Harness or golden corruption — re-capture Mu; never hand-edit goldens |

Package-specific fix hints live in that package's `COVERAGE.md`.

**Debug one scenario** (exception to full loop):

```bash
python3 src/test/golden/harness/run_scenario.py \
  --scenario src/test/golden/<package>/scenarios/<id>.py \
  --out /tmp/golden_debug --impl python \
  --mode <modeName> [--package <pkgDir>]   # when dir ≠ mode name
cat /tmp/golden_debug/diag.txt
python3 src/test/golden/harness/compare.py \
  --golden-dir src/test/golden/<package>/golden-mac/<id> \
  --actual-dir /tmp/golden_debug --dmax 0
```

(use `golden/` instead of `golden-mac/` on Linux; add `--no-xvfb` on macOS)

### Loop complete when

- `./run_migration_loop*.sh` exits **0**
- GUI sanity pixel reports judged acceptable (if any `NEEDS_AI_REVIEW`)
- Code review: no unresolved **blocking** findings
- Every `COVERAGE.md` item ✅ (or 🟡 with recorded justification)

Then ask the user about removing Mu sources and updating `PACKAGE`.

---

## Code review agent

The [five gates](#the-five-gates) check *behavior* — graph, pixels, runtime, defaults. None
read the *code*. Before treating a loop iteration as done, a fresh independent agent reviews
the actual diff for correctness — defects that pass every gate because the suite did not
exercise them.

**Scope: one iteration, not the whole branch.** Review the diff between the current commit
and its immediate parent (`git diff <parent>..HEAD`), not the full branch-vs-`main` history —
the latter is almost always far larger than what any one iteration actually touched, and
reviewing it wastes the agent's attention on code nobody just changed. Exclude binary/generated
artifacts (`golden/`, `golden-mac/` PNGs and `session.rv` files) — review the code that
produced them, not the artifacts themselves.

**Mechanism:** spawn a fresh `general-purpose` agent (there is no dedicated `code-reviewer`
agent type in this environment) with a prompt that gives it the specific commit range, the
context of what changed and why (a fresh agent has none of the implementing agent's context —
it must be given enough to make real judgment calls, not just told to "review this"), and
specific things to check per file. Have it report via the `ReportFindings` tool, ranked
most-severe first. **Do not** use the `/code-review` slash command for this — it's gated to
explicit user invocation only (`disable-model-invocation`) and cannot be called
programmatically by a loop.

**Enforcement:** blocking findings (wrong logic, unsafe assumptions, incomplete fixes) require
another fix-and-retry cycle. Non-blocking findings (style, minor nits) are reported but do
not fail the run.

Conditional step in the [migration loop](#migration-loop) (after gates 0–2 pass). The
orchestrator prints a reminder; the implementing agent spawns the reviewer and acts on
blocking findings.

---

## Definition of done

A package migration is accepted when:

1. Every coverage item in `COVERAGE.md` is ✅ (a passing golden scenario pins it).
2. [The five gates](#the-five-gates) pass via `./run_migration_loop*.sh` on the target
   platform(s).
3. [GUI sanity](#gui-sanity-real-display) has run: behavioral matches; pixel report reviewed
   and judged acceptable.
4. On macOS (if in scope): compare against `golden-mac/` — see [Mac-native capture](#mac-native-capture).
5. No item is left 🟡 without an explicit, recorded justification.
6. Any cross-package API the package exposes (callable from other Mu/Python packages)
   remains callable — verified by a scenario or integration check before the Mu source is
   removed.
7. The [code review agent](#code-review-agent) has run against this iteration's diff with no
   unresolved blocking findings.

## Allowed Operations

1. No file under golden/ or golden-mac/ shall be modified by hand — only
   capture_golden.sh / capture_golden_mac.sh may write them, and only when the
   determinism check passes
2. No more than 15 attempts at running all tests is allowed (15 iterations)
3. [GUI sanity](#gui-sanity-real-display) (`run_gui_sanity_gate.sh`) must run before a
   migration is considered done — behavioral is hard pass/fail; pixel is report-only and must
   be reviewed each run
4. golden/ and golden-mac/ are separate pixel spaces and must never be compared against each
   other or merged — a Mac capture failing against `golden/` (or a Linux capture failing
   against `golden-mac/`) is not a real signal, just a platform mismatch; always compare Mac
   output to `golden-mac/` and Linux output to `golden/`
5. Before calling an iteration done, run the [code review agent](#code-review-agent) on this
   iteration's diff (not the whole branch); blocking findings require another fix-and-retry
   cycle
