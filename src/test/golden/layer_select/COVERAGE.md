# `layer_select` — Migration Coverage Contract

**Purpose.** Exhaustive list of `layer_select` behaviors that MUST keep working when the
package is ported from Mu to Python. Each item maps to verification gate(s) and scenario id.
The port is done when every item here passes per [`../VERIFICATION.md`](../VERIFICATION.md).

**Source of truth.** Mu implementation:
`src/plugins/rv-packages/layer_select/layer_select_mode.mu` (~380 lines), `PACKAGE`,
`CMakeLists.txt`. Line numbers below refer to `layer_select_mode.mu` unless noted.

**Current blocker (Gate 2):** [`BLOCKER.md`](BLOCKER.md) — `LayerSelectRender` not activating
in harness; pixel gate fails until unblocked.

---

## File inventory (approved 2026-07-28)

| Path | Role | Migration action |
|---|---|---|
| `layer_select_mode.mu` | `LayerSelect : Widget` — GL margin HUD, layer list, input handlers | Port → `layer_select_mode.py`; remove after full package passes |
| `PACKAGE` | Mode registration, menu **Tools/Layer Selector**, shortcut `/`, `load: delay` | Update `modes:` entry to `layer_select_mode.py` when port lands |
| `CMakeLists.txt` | RVPKG target `layer_select` | Add `.py` to package install list when port lands |

**No existing Python** in this package. **No external callers** — no other packages import
`layer_select`; session_manager overlaps conceptually via `request.imageComponent` layer
sub-components (`sm_subcomponents`), not this widget.

**Files to create:**

| Path | Role |
|---|---|
| `layer_select_mode.py` | Python `LayerSelect` (`rvtypes.Widget`) + `createMode()` | **Drafted** — toggle via `RV_MODE_IMPL_layer_select_mode=python` |
| `layer_select_gl.py` | Mu `glyph`/`gltext` draw bridge for pixel parity in Python `render()` | Keep with Python port |
| `src/test/golden/layer_select/scenarios/*.py` | Golden scenarios (see tables below) |
| `src/test/golden/layer_select/run_all_goldens.sh` | Linux gate runner (Xvfb) |
| `src/test/golden/layer_select/run_all_goldens_mac.sh` | macOS gate runner (`golden-mac/`) |
| `src/test/golden/layer_select/run_migration_loop_mac.sh` | Migration loop orchestrator — scripts/env: [`../VERIFICATION.md`](../VERIFICATION.md#migration-loop); agent procedure: [`mu-python-migration` skill §5](../../../.agents/skills/mu-python-migration/SKILL.md) |
| `src/test/golden/layer_select/run_gui_sanity_gate.sh` | GUI sanity (orchestrator calls this after gates 1+2) |
| `src/test/golden/layer_select/fixtures/layers.env.example` | Document env vars for multi-layer EXR fixture |

**Harness:** mode name `layer_select_mode` ≠ package dir `layer_select`. Runners pass:

```bash
--mode layer_select_mode --package layer_select
```

See `run_scenario.py --package` and env overrides `LS_MODE` / `LS_PACKAGE` in
`run_all_goldens.sh`.

---

## Verification method

Gates (**B** / **P**), migration loop, capture, definition of done:
[`../VERIFICATION.md`](../VERIFICATION.md).

Coverage legend (from VERIFICATION.md): **✅** = pinned by a committed Mu golden (not “Python
verified yet”); **🟡** = outcome or pixels pinned but the specific UI trigger is not fully
pinned; **⬜** = no scenario or no committed golden yet.

Command-API scenarios pin **outcomes** (`request.imageComponent`, settings). Real
pointer/wheel/menu triggers are separate scenarios — **🟡** when the golden exists but the
behavioral artifact does not capture the trigger’s full effect (e.g. `ls_click_layer` golden
has empty `imageComponent` while `ls_select_layer` pins selection via API).

---

## Migration loop (this package)

General method: orchestrator in [VERIFICATION.md § Migration loop](../VERIFICATION.md#migration-loop); agent loop in [mu-python-migration skill §5](../../../.agents/skills/mu-python-migration/SKILL.md).

```bash
cd src/test/golden/layer_select
./run_migration_loop_mac.sh
```

**Harness:** `--mode layer_select_mode --package layer_select` (mode file stem ≠ package dir).
Env overrides: `LS_MODE`, `LS_PACKAGE`, `LAYER_EXR_FIXTURE`.

**Gate failure hints (this package):**

| Output | Fix focus |
|--------|-----------|
| Gate 1 | `request.imageComponent`, `LayerSelect` settings, mode lifecycle, layer names (`named_layers`) |
| Gate 2 | `layer_select_gl.py`, margin layout, GL text, docked/floating widget render |
| Gate 3 | Optional package + `ModeManagerPreload=layer_select_mode` in harness |

**Code review prompt context:** `LayerSelect` widget — GL margin layer list, EXR layer
selection via `request.imageComponent`, docked/floating, `/` shortcut; check
`LayerSelect` vs `layer_select_mode` naming and `layer_select_gl.py` bridge.

**Headless caveats** (`scenarios/_ls_common.py`): `/` via `mode-manager-toggle-mode`;
wheel events skipped (no `pixelInfo`); stylus uses QTest fallback.

---

## Port entry point

Python port target: `layer_select_mode.py` + `layer_select_gl.py` (Mu-backed GL text
drawing for pixel parity). Toggle: `RV_MODE_IMPL_layer_select_mode=python`.

**Port status:** Python implementation drafted; Mu baselines captured in `golden-mac/` (20
scenarios, 2026-07-28). Next: migration loop (`./run_migration_loop_mac.sh`).

---

## Fixtures

Multi-layer EXR is **required** for realistic layer names from `sourceMedia()`. No committed
fixture in-repo today.

Set **`LAYER_EXR_FIXTURE`** any way you like — shell export, CI env, or optional
`fixtures/layers.env` (gitignored). Runners source `layers.env` only if it exists.

Movieproc sources (`smptebars,…`) have no layers — usable only for activation/smoke, not
layer selection outcomes.

---

## A. Activation & lifecycle

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| A1 | `/` / `key-down--/` opens Layer Selector (activates mode) | PACKAGE:13-14, 205-218 | B | ✅ | `ls_activate_shortcut` |
| A2 | Menu **Tools/Layer Selector** activates mode | PACKAGE:12 | B | ✅ | `ls_activate_menu` |
| A3 | Mode loads delayed (`load: delay` in PACKAGE) — inactive until toggled | PACKAGE:15 | B | ✅ | `ls_activate`, `ls_activate_shortcut` |
| A4 | Widget renders layer list when multi-layer source is current view | 230-371 | P | ✅ | `ls_widget_docked` |
| A5 | Widget hidden / no draw when source has no layers | 254, 248 | P | ✅ | `ls_no_layers` (movieproc) |

## B. Layer selection (core outcome)

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| B1 | Click release on row selects layer → `setStringProperty(...)` | 65-98, 110-128 | B | 🟡 | `ls_select_layer`, `ls_click_layer` |
| B2 | Select **Default** (index 0) clears request → `imageComponent = []` | 84-86, 295 | B | ✅ | `ls_select_default` |
| B3 | Middle click (`pointer-2--push`) commits highlighted layer | 217, 65-98 | B | 🟡 | `ls_middle_click_layer` |
| B4 | Wheel up/down moves highlight (`selectLayer`, ±1) without committing | 43-63, 214-215 | P | ✅ | `ls_wheel_highlight`, `ls_wheel_up` |
| B5 | Hover motion updates highlight index (`handleMotion`) | 130-171 | P | ✅ | `ls_hover_highlight` |
| B6 | Leaving widget resets highlight to active layer (+1 if non-default) | 134-143 | P | ✅ | `ls_hover_highlight` |
| B7 | Active layer markers reflect current `request.imageComponent` on render | 256-292, 350-356 | P | ✅ | `ls_widget_docked` |
| B8 | Selection uses `pixelInfo` source when setting layer; render uses `sourcesRendered` | 47-51, 234-240 | B | ✅ | `ls_select_layer` |

## C. Docked vs floating layout

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| C1 | Default: docked in left margin (`readSetting LayerSelect/widgetIsDocked` default true) | 223-227 | P | ✅ | `ls_widget_docked` |
| C2 | Right-click → **Floating Selector** toggles docked/floating | 194-201, 173-187 | B+P | ✅ | `ls_floating_toggle`, `ls_popup_menu` |
| C3 | Floating: `drawInMargin(-1)`, widget draggable (`pointer-1--drag`) | 179-184, 209, 313-322 | P | ✅ | `ls_widget_floating`, `ls_widget_drag` |
| C4 | Docked: left margin band + vertical centering | 311-322, 301-309 | P | ✅ | `ls_widget_docked` |
| C5 | `writeSetting LayerSelect/widgetIsDocked` persists across sessions | 176, 223 | — | — | Dropped — RV settings, not in `session.rv` B gate |

## D. Input parity & chrome

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| D1 | Stylus pen bindings mirror pointer (push/move/release/drag) | 210-213 | B+P | 🟡 | `ls_stylus_select` |
| D2 | Close button when pointer near top-left (`drawCloseButton`, `_inCloseArea`) | 360-365, 158-168 | P | ✅ | `ls_close_hover`, `ls_close_click` |
| D3 | Drag moves floating widget position | 209, Widget.drag | P | ✅ | `ls_widget_drag` |

---

## Dropped (no equivalent golden test)

| Behavior | Reason |
|---|---|
| Error-frame styling (`isCurrentFrameError` branch) | Requires broken/decode-fail media; non-deterministic in headless gate |
| Print-on-exception in `setSelectedLayer` / `getStringProperty` | Diagnostic only; not user-visible outcome |
| `_drawOnPresentation = true` after wheel | Internal presentation flag; no stable B/P artifact |
| `LayerSelect/widgetIsDocked` persistence across RV restarts | Stored in RV settings, not captured by `saveSession` behavioral gate |

---

## Scenarios (20 total)

| Id | Gates | Fixture | Trigger |
|---|---|---|---|
| `ls_activate` | B | movieproc | `activateMode` API |
| `ls_activate_shortcut` | B | movieproc | real `/` shortcut |
| `ls_activate_menu` | B | movieproc | real Tools menu |
| `ls_deactivate_shortcut` | B | movieproc | `/` toggle off |
| `ls_no_layers` | B+P | movieproc | — |
| `ls_select_layer` | B | EXR | command API (outcome) |
| `ls_select_default` | B | EXR | command API |
| `ls_click_layer` | B+P | EXR | real click (approx. coords) |
| `ls_middle_click_layer` | B | EXR | wheel + middle click |
| `ls_wheel_highlight` | B+P | EXR | wheel down |
| `ls_wheel_up` | B+P | EXR | wheel down + up |
| `ls_hover_highlight` | B+P | EXR | pointer move in/out |
| `ls_widget_docked` | B+P | EXR | docked viewport |
| `ls_widget_floating` | B+P | EXR | floating viewport |
| `ls_widget_drag` | B+P | EXR | real pointer drag |
| `ls_floating_toggle` | B+P | EXR | popup toggle / settings fallback |
| `ls_popup_menu` | B+P | EXR | right-click menu PNG |
| `ls_close_hover` | B+P | EXR | close-button hover |
| `ls_close_click` | B+P | EXR | close-button click |
| `ls_stylus_select` | B+P | EXR | stylus pen events |

Runners: `run_all_goldens_mac.sh`, `capture_golden_mac.sh`. EXR scenarios require
`LAYER_EXR_FIXTURE` (committed fixture: `fixtures/test_layers.exr`). Mu baselines in
`golden-mac/` (20 scenarios, 2026-07-28).

---

## Status summary

Scenarios (**20**); Python port drafted; **Mu baselines committed** in `golden-mac/`.
Status column tracks Mu golden coverage (✅/🟡), not Python port pass/fail — run the migration
loop for that.

**Next checkpoints:**

1. ~~User approves file inventory~~ ✓
2. ~~EXR fixture (`fixtures/test_layers.exr`)~~ ✓
3. ~~Capture Mu baselines (`capture_golden_mac.sh`)~~ ✓
4. Run migration loop: `./run_migration_loop_mac.sh` until exit 0 ([skill §5](../../../.agents/skills/mu-python-migration/SKILL.md); [Definition of done](../VERIFICATION.md#definition-of-done))
