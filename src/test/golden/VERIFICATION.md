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
| `run_scenario.py` | Launches RV headless (Xvfb + software Mesa), runs an in-process scenario, collects artifacts into an out dir. Pass `--impl mu\|python` and optional `--mode` to select implementations (see [toggle section](#mupython-implementation-toggle)). |
| `compare.py` | Behavioral gate (normalized GTO diff) + pixel gate (`rmsImageDiff`). Exit 0 = PASS. |

### Layout per package
```
src/test/golden/
  VERIFICATION.md            # this file (shared method)
  harness/                   # shared run_scenario.py + compare.py
  <package>/
    COVERAGE.md              # package-specific behavior inventory + file list
    scenarios/<id>.py        # in-RV scenarios (command-API driven; QTest for DnD)
    golden/<id>/             # committed baselines: session.rv (+ panel.png)
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

## Definition of done (per migration slice)

A slice of a Python port is accepted when:
1. Every coverage item in that slice is ✅ (a passing golden scenario pins it).
2. Both gates pass at `-dmax 0` against the Mu-captured goldens.
3. No item in the slice is left 🟡 without an explicit, recorded justification.
4. Any cross-package API the slice exposes (callable from other Mu/Python packages)
   remains callable — verified by a scenario or integration check before the Mu source is
   removed.


## Allowed Operations

1. No file under golden/ shall be modified