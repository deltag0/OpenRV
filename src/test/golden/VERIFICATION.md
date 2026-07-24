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

## The two gates

Both are HARD: a scenario passes only if **both** pass. They catch disjoint regression
classes, so neither subsumes the other.

- **Behavioral gate (B)** — after a scripted scenario, the node graph must match the Mu
  golden exactly: node set, types, connections, and persistent properties, captured via
  `saveSession(sparse=False)` → normalized text GTO. Catches wrong graph mutations,
  property writes, and connections — the *logic*.
- **Pixel gate (P)** — the relevant panel/dialog/editor grabbed to PNG and compared at
  `rmsImageDiff -cmp -dmax 0` on the pinned Xvfb + software-Mesa path. Catches *visual*
  regressions the graph can't see — layout, icons, status marks, widget state.

Some behaviors are observable only one way (a hover swap is P-only; a property write with
no visible change is B-only). Each inventory item records which gate(s) apply.

## Coverage status legend

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
| `run_scenario.py` | Launches RV headless (Xvfb + software Mesa), runs an in-process scenario, collects artifacts into an out dir. Pass `--impl mu\|python` and optional `--mode` to select implementations (see [toggle section](#mupython-implementation-toggle)). Runs `golden_bootstrap.py` before each scenario. |
| `golden_bootstrap.py` | In-RV pre-scenario hook: activates `source_setup` when `GOLDEN_SOURCE_SETUP=1` (set automatically for `tree_readonly.py`). |
| `compare.py` | Behavioral gate (normalized GTO diff) + pixel gate (`rmsImageDiff`). Exit 0 = PASS. |

### Package runners (`session_manager`)

| File | Role |
|---|---|
| `session_manager/run_all_goldens.sh` | **Required migration gate (Linux)** — runs every scenario (except integration/diagnostic skips), then `compare.py` at `-dmax 0` against `golden/`. Default `IMPL=python`; use `IMPL=mu` to verify Mu determinism or re-baseline. |
| `session_manager/run_gui_sanity_gate.sh` | **Second required gate** — re-runs the same scenarios against a real on-screen display (no Xvfb), still compared against `golden/` (the Linux baselines). Behavioral check is hard pass/fail; pixel differences are reported (RMS + max-diff + PNG paths), not scripted, and must be reviewed. See [GUI sanity gate](#gui-sanity-gate-real-display) below. |
| `session_manager/run_all_goldens_mac.sh` | **Required migration gate (macOS)** — same shape as `run_all_goldens.sh`, but self-consistently Mac-native: real display (macOS has no Xvfb), compared against `golden-mac/` (never against `golden/` — see [Mac-native gate](#mac-native-gate)). Hard pass/fail on both behavioral and pixel. |
| `session_manager/capture_golden.sh` | Capture Mu baselines into `golden/<id>/` on Linux (`--impl mu` via `run_scenario.py`, under Xvfb). |
| `session_manager/capture_golden_mac.sh` | Capture Mu baselines into `golden-mac/<id>/` on macOS (real display). Captures each scenario twice and refuses to commit unless both captures are byte-identical — see [Mac-native gate](#mac-native-gate). |
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
    golden/<id>/             # committed Linux baselines: session.rv (+ panel.png)
    golden-mac/<id>/         # committed macOS baselines: session.rv (+ panel.png) --
                              # separate pixel space from golden/, see Mac-native gate
```

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

## Determinism requirements for the pixel gate

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

## GUI sanity gate (real display)

`run_all_goldens.sh` above is deterministic, but it pins exactly one rendering path: Xvfb +
software Mesa. A port can pass that gate while being visibly broken under a real
GPU/compositor/font stack — or, less obviously, the reverse: differ from Mu only because of
environment noise the headless path can't see. `<package>/run_gui_sanity_gate.sh` exists to
catch that class of regression by re-running the same scenarios against a real on-screen
display instead of Xvfb.

This is a **required gate, not a smoke test — but it is deliberately not a scripted pixel
pass/fail.** It runs two independent checks per scenario:

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

**Final phase: launch like a normal app, no `--impl` at all.** Added 2026-07-24 after a
real bug — `session_manager`'s panel was unreachable via its real `x` shortcut/menu on a
genuinely normal launch — that every gate in this repo missed, including this one's own main
loop above. The reason: every gate always forces an explicit `RV_MODE_IMPL_<mode>` (needed
for the Mu-vs-Python comparison the rest of this gate does), so none of them ever exercised
RV's actual default mode-selection logic — which is exactly where the bug lived
(`preferPythonImpl()`'s hardcoded-default branch behaved differently from the same env var
being literally present, for reasons that resisted `print()`-based tracing — see the fix in
`src/bin/nsapps/RV/main.cpp` and `mode_manager.mu`). Confirmed by direct reproduction: reverting
the fix and re-running this exact scenario with no impl override produced `panel(sessionManager)
found: False` / `PANEL NOT FOUND -- no panel.png written`, which `compare.py`'s missing-artifact
rule turns into a hard FAIL regardless of pixel mode.

This phase re-runs every non-skipped scenario one more time via `run_scenario.py --impl
default` (a real, first-class option — not a throwaway env var — that sets no
`RV_MODE_IMPL_*` at all, letting RV pick its own shipped default exactly as a normal launch
would). It is a **hard gate**: missing artifacts and behavioral mismatch fail it, the same
rule as everywhere else in this doc. It does not replace the main loop's Mu-vs-Python
comparison — the two are complementary: the main loop asks "does the *implementation* I
selected behave correctly," this phase asks "does *selecting no implementation at all* still
work."

**Known bug, `sm_meridian_mp4_load` and `sm_media_add_sources` skipped:** both use
`addSources()` + `waitForProgressiveLoading()`, which hangs forever under a real display
(confirmed 2026-07-24 — native, not fixable from the Python/test side; neither Qt
event-pumping nor a forced synchronous repaint on the real GL widget advances it). Since this
script always runs `--no-xvfb`, both are in its `SKIP_IDS` until the underlying render/load
path is fixed.

---

## Mac-native gate

Unlike the GUI sanity gate above (real display, but still judged against the *Linux*
`golden/` baselines, so pixel is report-only), the Mac-native gate is a **third, fully
self-consistent, hard pass/fail gate scoped to macOS**: Mac output is compared only against
Mac-captured baselines in `golden-mac/`, via `run_all_goldens_mac.sh` /
`capture_golden_mac.sh`. It does not replace or get reconciled with `golden/` — the two
pixel spaces are not comparable (see below) and are never diffed against each other.

**Why this is viable as a real gate, not just a sanity check** (verified empirically
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

## Definition of done (per migration slice)

A slice of a Python port is accepted when:
1. Every coverage item in that slice is ✅ (a passing golden scenario pins it).
2. On Linux: both gates pass at `-dmax 0` against the Mu-captured goldens headlessly
   (`run_all_goldens.sh`), **and** the GUI sanity gate (`run_gui_sanity_gate.sh`) exits clean
   (behavioral matches) **and** its pixel report has been reviewed and judged acceptable —
   see [GUI sanity gate](#gui-sanity-gate-real-display). On macOS (if that platform is in
   scope for the slice): `run_all_goldens_mac.sh` passes at `-dmax 0` against `golden-mac/`
   — see [Mac-native gate](#mac-native-gate).
3. No item in the slice is left 🟡 without an explicit, recorded justification.
4. Any cross-package API the slice exposes (callable from other Mu/Python packages)
   remains callable — verified by a scenario or integration check before the Mu source is
   removed.


## Allowed Operations

1. No file under golden/ or golden-mac/ shall be modified by hand — only
   capture_golden.sh / capture_golden_mac.sh may write them, and only when the
   determinism check passes
2. No more than 15 attempts at running all tests is allowed (15 iterations)
3. The GUI sanity gate (`run_gui_sanity_gate.sh`) must also be run before a slice is
   considered done: its behavioral check is a hard gate; its pixel report has no scripted
   threshold and must be reviewed and judged each run (see
   [GUI sanity gate](#gui-sanity-gate-real-display)) — do not treat the script's exit code
   alone as a substitute for that review, and do not add a scripted pixel threshold to paper
   over a judgment call
4. golden/ and golden-mac/ are separate pixel spaces and must never be compared against each
   other or merged — a Mac capture failing against `golden/` (or a Linux capture failing
   against `golden-mac/`) is not a real signal, just a platform mismatch; always compare Mac
   output to `golden-mac/` and Linux output to `golden/`