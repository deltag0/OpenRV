# `session_manager` — Migration Coverage Contract

**Purpose.** This is the exhaustive list of `session_manager` behaviors that MUST keep
working when the package is ported from Mu to Python. Each item is mapped to how it is
verified (which gate, which golden scenario) and its current coverage status. A Python
port is "done" for a slice only when every item in that slice is covered by a passing
golden scenario.

**Source of truth.** The Mu implementation:
`src/plugins/rv-packages/session_manager/` — `session_manager.mu` (generated from
`session_manager.mu.in`), the `*_edit_mode.mu` editors, `transform_manip.mu`,
`local_thumbnail_gen.py`, the `.ui` files, and the `PACKAGE`. Line numbers below refer to
`session_manager.mu` unless another file is named.

---

## Verification method

The gates (Behavioral **B** / Pixel **P**), the coverage-status legend (✅/🟡/⬜), the
headless run recipe, determinism rules, and the per-slice definition of done are **shared
across all package migrations** and defined in
**[`../VERIFICATION.md`](../VERIFICATION.md)** — read that first. This file is the
`session_manager`-specific inventory that plugs into that method: the **Gate** column of
each table below is B/P per that doc, and ✅ means "pinned by a committed Mu golden," not
"verified in the Python port." Because the committed scenarios drive via the `rv.commands`
API, they pin the *resulting graph state and panel appearance* (the reactive/display half),
not the *UI trigger* (click/drag/menu). So an item is **🟡** when its outcome is pinned but
its specific trigger isn't exercised. Behaviors with no equivalent test are dropped
(see [Dropped](#dropped-no-equivalent-golden-test)), so every row is ✅ or 🟡.

A growing set of items now have a **real-click** scenario written (using
`QTest.mouseClick`/`QTest.keyClicks` via `harness/qt_scenario_utils.py` — plain clicks are
not subject to the drag/drop limitation in §G, only the drag *gesture* is blocked
headlessly), closing the "trigger not exercised" half of 🟡. Where noted **⬜ baseline
capture pending**, the scenario exists and is believed correct but has no committed
`golden/<id>/` yet (requires the pinned Linux + Xvfb + software-Mesa path — see
`../VERIFICATION.md`); the row's status marker reflects only what has a committed golden
today and should flip once captured.

Scenarios and their committed baselines live in `scenarios/` + `golden/`; the tables
below name the scenario pinning each behavior and its status.

## Port entry point

Python port lives under `src/plugins/rv-packages/session_manager/`:
`session_manager.py` (`SessionManagerMode` + `createMode()`), with
`session_manager_support.py`, `session_manager_tree.py`, and
`session_manager_interactions.py` (toolbar/menu wiring required for
`tree_readonly` panel pixels). Toggle with `RV_MODE_IMPL_session_manager=python`
(or `RV_PREFER_PYTHON_MODES`); the harness prepends package source to
`PYTHONPATH` and sets `RV_PYTHONPATH_APPEND_ONLY=1` so edits load without rebuild
(staged `PlugIns/Python/` must not shadow source — remove stale copies after
rebuild if golden runs pick up old artifacts).

**Slice 1 (read-only tree, `tree_readonly`):** Python verified green on macOS
(`run_all_goldens_mac.sh`, `golden-mac/tree_readonly`, `-dmax 0`) as of 2026-07-25.
Mu sources remain in place.

---

## A. Activation & panel lifecycle

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| A1 | `x` / `key-down--x` toggles the dock panel visible/hidden | PACKAGE:14 | P | 🟡 | `tree_readonly` (opens only) |
| A3 | Panel is a left-docked `QDockWidget` titled "Session Manager" | 3195,3278 | P | 🟡 | `tree_readonly` |

## B. Tree view — structure & display

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| B1 | Nodes bucketed into FOLDERS/SOURCES/SEQUENCES/STACKS/LAYOUTS/OTHER headers | 2133-2179 | B+P | ✅ | `tree_readonly` |
| B2 | Category headers non-selectable, styled, size-hinted | 2144-2152 | P | ✅ | `tree_readonly` |
| B3 | Per-node type icon (`iconForNode`) | 3303-3314 | P | ✅ | `tree_readonly` |
| B4 | Current-view node marked with "✔" in status column | 1323,1585 | P | 🟡 | `tree_readonly` |
| B5 | Categories sorted; rows sorted (`sort(0, Ascending)`) | 2206 | B+P | ✅ | `tree_readonly` |
| B6 | Category expansion persisted via `#Session.sm_view.<CATEGORY>` | 2188-2202 | B | ✅ | `sm_expansion` |
| B7 | Node expansion persisted (`sm_state.expandState`) | 208-241 | B | ✅ | `sm_expansion` |
| B8 | Empty categories omitted | 2183 | P | ✅ | `tree_readonly` |
| B9 | Source rows render preview widget when previews enabled | 1850-1923 | P | 🟡 | `tree_readonly` (fallback icon; see §H) |

## C. Node creation (Add / Folder / dialogs)

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| C1 | Add ▸ Sequence/Stack/Switch/Folder/Layout/Retime create the right node type | 3348-3353,3382-3387 | B+P | ✅ | `sm_create_views`; real `addButton` click + "New Viewable" menu: `sm_button_add_menu` (⬜ baseline capture pending) |
| C2 | Add ▸ Color / OCIO / Dynamic (Dynamic gated by `RV_ENABLE_DYNAMIC_NODE`) | 3365-3370 | B | ✅ | `sm_create_nodes` |
| C3 | Selected nodes become inputs of the new node; auto-named (`renameByType`) | 2522-2538,2281-2314 | B | 🟡 | `sm_create_views` (inputs pinned; auto-name not) |
| C5 | Create Image dialog: SRGB/ACES charts, color bars, black, color, blank → movieproc source | 2564-2681 | B | ✅ | `sm_create_image` (movieproc outcome; modal dialog UI not gated) |
| C8 | New Folder: empty / from selection (reparent) / from copy | 2699-2753 | B | ✅ | `sm_folders`; real `folderButton` click + "From Selection", real media: `sm_button_folder_menu` (⬜ baseline capture pending -- macOS smoke-testing hit an unexplained hang clicking `folderButton`'s popup itself, unproven on the Linux target; see scenario docstring) |
| C9 | Created group made current via `setViewNode` | 2534,2752 | B | ✅ | `sm_create_views` |

## D. View switching & navigation

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| D1 | Double-click tree node → `setViewNode` | 1343-1373 | B | 🟡 | `sm_view_switch` (outcome pinned; click not) |
| D2 | Single-click top-level selection → becomes current view | 1466-1484 | B | 🟡 | `sm_view_switch` (outcome pinned; click not) |
| D3 | Status-column click views a sub-component (`setImageRequest`) | 1375-1389,530 | B | 🟡 | `sm_subcomponents` (request.imageComponent pinned; click not) |
| D4 | Prev/Next nav buttons → `previous/nextViewNode` | 3085-3101 | B+P | 🟡 | `sm_nav` (nav outcome pinned); real `prevViewButton`/`nextViewButton` clicks: `sm_button_nav_prev_next` (⬜ baseline capture pending) |
| D5 | Nav buttons enabled/label state (`viewLabel` + prev/next enabled) | 1565-1574 | P | ✅ | `sm_nav` (nav-panel pixels) |
| D7 | `after/before-graph-view-change` keep tree ✔, nav, tab, edit-UI in sync | 1576-1637 | B+P | ✅ | `sm_view_switch` |

## E. Inputs tab

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| E1 | Inputs list reflects `nodeConnections` of the current view node | 1486-1534 | B+P | ✅ | `sm_inputs` |
| E3 | Reorder up/down → `setInputs` new order | 2806-2860 | B | 🟡 | `sm_inputs_reorder` (order pinned); real media: `sm_media_reorder_command`; real `orderUpButton`/`orderDownButton` click + real media: `sm_media_reorder_button` (⬜ baseline capture pending) |
| E4 | Sort A-Z / Z-A → `setInputs` sorted (folders also `setSortKeyInParent`) | 2871-2930 | B | 🟡 | `sm_inputs_sort` (sorted order pinned); real `sortAscButton`/`sortDescButton` click + real media: `sm_button_sort_buttons` (⬜ baseline capture pending) |
| E5 | Delete input → `setInputs` minus selection | 3022-3052 | B | 🟡 | `sm_inputs_delete` (outcome pinned); real `inputsDeleteButton` click + real media: `sm_media_inputs_delete_button` (⬜ baseline capture pending) |
| E6 | Inputs list disabled for source-type view node | 1594-1597 | P | ✅ | `sm_view_switch` (final view is a source) |

## F. Edit tab & per-view edit modes

The Edit tab hosts editors contributed by sibling modes via the `session-manager-load-ui`
event. Each edit mode writes specific `#RV*` properties. **All B-gate** (property writes),
plus **P** for the editor widget rendering.

| # | Edit mode | Properties written | Ref | Status | Scenario |
|---|---|---|---|---|---|
| F1 | Composite | `#RVStack.composite.type`, `.dissolveAmount` | Composite_edit_mode.mu:49,76 | ✅ | `sm_edit_composite` |
| F2 | FolderGroup | `#RVFolderGroup.mode.viewType` (+ swaps child modes) | FolderGroup_edit_mode.mu:52 | ✅ | `sm_edit_folder` |
| F3 | LayoutGroup | `#RVLayoutGroup.layout.mode/.spacing/.gridRows/.gridColumns` | LayoutGroup_edit_mode.mu:54-67 | ✅ | `sm_edit_layout` |
| F4 | RetimeGroup | `#RVRetime.visual/audio.scale/offset`, `.output.fps` | RetimeGroup_edit_mode.mu:39-195 | ✅ | `sm_edit_retime` |
| F5 | SequenceGroup | `#RVSequence.mode.autoEDL/useCutInfo`, `.output.fps/size`, `#RVSequenceGroup.timing.retimeInputs` | SequenceGroup_edit_mode.mu:94-214 | ✅ | `sm_edit_sequence` |
| F6 | SourceGroup | `#RVFileSource.cut.in/out/syncGui` (+ `setInPoint/OutPoint`) | SourceGroup_edit_mode.mu:55-149 | ✅ | `sm_edit_source` |
| F7 | Stack | `#RVStack.mode.*`, `.output.chosenAudioInput/fps/size`, `#View.timing.retimeInputs` | Stack_edit_mode.mu:186-328 | ✅ | `sm_edit_stack` |
| F8 | StackGroup | activates Composite+Stack; wipes from `<view>.ui.wipes` | StackGroup_edit_mode.mu:40-105 | ✅ | `sm_edit_stackgroup` (ui.wipes + composite pinned; wipe GL not) |
| F9 | Switch | `#RVSwitch.mode.*`, `.output.input/size/autoSize` | Switch_edit_mode.mu:141-220 | ✅ | `sm_edit_switch` |
| F10 | SwitchGroup | (activates Switch_edit_mode only) | SwitchGroup_edit_mode.mu | ✅ | `sm_edit_switchgroup` |
| F11 | transform_manip | `<tform>.transform.translate/scale/rotate`, `.tag.tmanip*` | transform_manip.mu:240-362 | ✅ | `sm_transform_manip` (props via equivalent commands; pointer gesture not) |
| F13 | Per-node tab selection persisted (`sm_state.tab`); source groups default to Edit tab | 3054-3076 | ✅ | `sm_tabs` |

## G. Drag & drop

Real drag gestures can't be driven headlessly — synthesized `QDropEvent`s have a null
`source()`, so the Mu `NodeTreeView` internal-drag path never runs (verified 2026-07-22).
We do **not** chase the modal `QDrag.exec()`; instead we pin the drag **outcomes** with the
equivalent `rv.commands`. The drag *gesture* is a port-side interaction detail, not gated
here.

| # | Behavior (outcome) | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| G1 | Reparent (move): node leaves old folder, joins new (`setNodeInputs` on both) | 1391-1448 | B | ✅ | `sm_reparent` |
| G2 | Reparent (copy): node added to new folder, kept in old | 1409 | B | ✅ | `sm_reparent_copy` |
| G5 | Folder child sort order (`setSortKeyInParent`) | 977-998,482 | B | ✅ | `sm_folder_sort` |

**Not gated here** (no command equivalent / handler-internal — verify on the Python port):

- **G3/G4** drop guards (reject non-col-0 / drop-on-self / FOLDERS-root-with-non-folders) —
  pure `dragEnter/dragMove` accept-reject logic with no graph outcome to capture.
- **G6** `NodeModel.mimeData` `rvnode://TYPE/NODE[/media]` URL format — feasible via a direct
  `mimeData()` call (no drag; verified reachable), but needs a text-artifact gate with
  authority (`user@host:port`) normalization. Follow-up if we want it gated.
- **G7/G8** inputs-DnD — same drag limitation; the graph outcome overlaps §E inputs scenarios.

## H. Source previews / thumbnails / filmstrip  ⚠️ nondeterminism

Provided by `local_thumbnail_gen.py` (a separate `load: immediate` Python mode) via
`rvio` subprocesses, communicated over internal events. **Async and timing-dependent.**

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| H1 | Real thumbnail replaces fallback icon once `rvio` preview job completes | 1877-1888,3188 | P | ⬜ | `sm_media_load`, `sm_mp4_load` (baseline capture pending) |
| H2 | Real filmstrip becomes available alongside the thumbnail | 1883-1888 | P | ⬜ | `sm_media_load`, `sm_mp4_load` (baseline capture pending) |
| H4 | Fallback `fallback_thumbnail.png` until real preview arrives | 3322,1867 | P | ✅ | `tree_readonly` |
| H5 | `session-manager-preview-available` quiesce point: capture is deterministic once every source's thumbnail+filmstrip files exist | 3188 | P | ⬜ | `sm_media_load`, `sm_mp4_load` (baseline capture pending); integration: `sm_mp4_all` with `SM_TEST_MP4_QUIESCE=1` |

> **Determinism rule:** default pilot fixtures use media-free sources and capture with
> the fallback icon (H4), which is deterministic. Real-preview scenarios (H1/H2/H5) now
> quiesce via `_sm_common.quiesce_real_previews`, which polls
> `session-manager-get-thumbnail-path`/`-filmstrip-path` for every source until both exist
> on disk (raising on timeout) before any capture. **Open risk, not yet verified:** this
> assumes `local_thumbnail_gen.py`'s `rvio` subprocess encode is bit-reproducible run-to-run
> the same way software-Mesa GL rendering is — untested from this machine. Before trusting
> `-dmax 0` on `sm_media_load`'s `panel.png`, run it twice on the capture machine and
> `rmsImageDiff -cmp -dmax 0 -m` the two outputs directly; if not bit-identical, do not
> loosen `dmax` (policy) — instead crop/placeholder the preview thumbnail sub-region out of
> the capture before diffing, per the option already documented above.

## I. Toolbar buttons & context menus

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| I1 | Button bar: Create View / Folder / Delete / Edit Info / Configure / Select Current | 3280-3345 | P | 🟡 | `tree_readonly` (rendered) |
| I7 | Inline rename (Edit key / Edit Info button, objectName `renameButton`) → `setUIName` | 1449-1463,2798 | B | 🟡 | `sm_rename` (setUIName pinned); real `renameButton` click + inline `QLineEdit` type/commit: `sm_button_rename_inline` (⬜ baseline capture pending — highest-risk scenario in this batch; if unreliable headlessly, stays 🟡 with this note as the recorded justification per `../VERIFICATION.md`'s DoD rule 3, not silently forced to pass) |
| I8 | Delete View: `removeInput` if multi-parent folder child, else `deleteNode` | 2755-2784 | B | 🟡 | `sm_delete` (deleteNode pinned); real media: `sm_media_delete_command`; real `deleteButton` click, single-parent: `sm_media_delete_button`; real `deleteButton` click, multi-parent (`removeInput` branch, previously untested): `sm_button_delete_multiparent` (⬜ baseline capture pending) |
| I9 | Select Current button (`selectCurrentButton`) → `selectViewableNode` re-syncs tree selection to the current view node (does not change the view) | 1536-1563 | P | ⬜ | `sm_button_select_current` (baseline capture pending) |
| I10 | Configure button (`configButton`) popup: startup radio group + "Show Source Previews" toggle | 3451-3474 | P | ⬜ | `sm_button_config_menu` (pixel-only — settings aren't in the session dump; baseline capture pending) |

## J. Settings, persistence & private properties

| # | Behavior | Ref | Gate | Status |
|---|---|---|---|---|
| J5 | Per-node `sm_state.tab/sortKey/sortKeyParent/expandState/expandedSubState/toolTip` | 168-332,3056 | B | ✅ | `sm_tabs`/`sm_folder_sort`/`sm_expansion` (toolTip/expandedSubState not) |
| J7 | `#Session.sm_view.<CATEGORY>`, `#Session.sm_window.splitter` | 2188,1203 | B | ✅ | `sm_expansion` (sm_view pinned; splitter not) |
| J8 | `<source>.request.imageComponent` (sub-component selection) | 519-606 | B | ✅ | `sm_subcomponents` |

## K. Events — the behavioral contract

**Bound events (main mode, 3172-3189):** `new-node`, `source-modified`,
`source-group-complete`, `before/after-progressive-loading`, `after-node-delete`,
`after-clear-session`, `after/before-graph-view-change`, `graph-node-inputs-changed`,
`graph-state-change`, `key-down--@` (debug), `before-session-deletion`,
`view-edit-mode-activated`, `event-category-state-changed`,
`session-manager-preview-available`. Each must trigger the same handler effect (tree
rebuild / inputs update / nav update / UI reload) in the port.

**Internal events SENT:** `session-manager-load-ui`, `session-manager-get-thumbnail-path`,
`session-manager-get-filmstrip-path`, `session-manager-previews-disabled/-enabled`.

**Suppression flags:** `_progressiveLoadingInProgress` and `_disableUpdates` gate whether
events rebuild the tree (1488, 2221) — the port must suppress on the same windows or the
behavioral gate will see spurious rebuilds.

| # | Behavior | Gate | Status | Scenario |
|---|---|---|---|---|
| K1 | Adding a source fires `new-node` → tree rebuild | B+P | ✅ | `tree_readonly` |
| K2 | `after-clear-session` rebuilds empty tree | B+P | ✅ | `sm_clear` |
| K4 | `graph-node-inputs-changed` updates inputs of current view | B | ✅ | `sm_inputs_delete` |

## L. Custom Qt subclasses — implementation to reproduce in PySide6

These are behaviors, not just classes — each override has observable effects the gates
must pin. (Details: `session_manager.mu`.)

| # | Class : base | Overridden virtuals | Ref |
|---|---|---|---|
| L1 | `ThumbnailWidget : QLabel` | (none; scaled pixmap) | 614-632 |
| L2 | `FilmstripWidget : QLabel` | `mouseMoveEvent` → scrub | 636-680 |
| L3 | `SourcePreviewWidget : QWidget` | `event` (HoverEnter/Leave swap) | 684-727 |
| L4 | `NodeModel : QStandardItemModel` | `mimeTypes`, `mimeData` (rvnode:// URLs) | 729-798 |
| L5 | `NodeTreeView : QTreeView` | `dragEnterEvent`, `dragMoveEvent`, `dropEvent` | 815-1008 |
| L6 | `InputsView : QListView` | `dragEnterEvent` (force copy), `dropEvent` | 1017-1053 |
| L7 | `EventFilter : QObject` | `eventFilter` → forwards to main view widget | 1056-1068 |
| L8 | Timer pattern | `_sortTimer/_dropTimer/_lazyUpdateTimer` defer work until model consistent | 809-813 |

## M. Resources, .ui files & Qt5/6 tokens

| # | Item | Ref | Note |
|---|---|---|---|
| M1 | `.ui` loaded: `session_manager.ui`, `new_node.ui`, `create_image_dialog.ui` | 3196,2546,2570 | via `loadUIFile`(port: `QUiLoader`) |
| M2 | Editor `.ui`: composite/folder/layout/retime/sequence/source/stack/switch | (edit modes) | one per F1–F9 |
| M3 | Icons via `auxIcon` from Qt resource `:images/` (qrc-compiled) | 1188-1193 | port must register/qrc these PNGs |
| M4 | `colorAdjustedIcon` light/dark variants using palette | 1156-1178 | dark-UI theming |
| M5 | Token `@MU_QT_QDRAGMOVEEVENT_POSITION@` → `event.position().toPoint()` | .mu.in 677,922 | Qt6 API at runtime |
| M6 | Token `@MU_QT_QPALETTE_COLORROLE@` → `QPalette.Window` | .mu.in 1158 | Qt6 API at runtime |

## N. Integration touchpoints

| # | Item | Ref | Note |
|---|---|---|---|
| N1 | `local_thumbnail_gen.py` companion mode (load: immediate) | PACKAGE:39 | preview producer; may migrate separately |
| N2 | Depends on Mu modules `rvui`, `app_utils`, `extra_commands` | 7-15 | port must call Python equivalents |
| N3 | Uses `psutil` (suspend/resume rvio) in the Python thumbnail mode | :5 | dependency already Python |
| N4 | Reacts to session lifecycle (clear/delete/read); rebuilds from `viewNodes()` | 3173-3189 | state is derived, not persisted |
| N5 | No `sync`/network coupling; DnD `rvnode://` URIs are local only | (verified) | rules out a whole risk class |
| N6 | Build: `session_manager.mu.in` → `.mu` via CMake; rvpkg globs whole dir | CMakeLists.txt:27,29 | port is `.py`, no configure_file needed |

---

## Files involved in the migration

Base dir `P/ = src/plugins/rv-packages/session_manager/`. Status of each file under the
Mu→Python port.

### O.1 Mu sources to PORT then remove (the actual translation work)

| File | Role | Notes |
|---|---|---|
| `P/session_manager.mu.in` | **source of truth** for the main mode (3577 lines) | `@MU_QT_*@` tokens (M5/M6) become runtime Qt6 calls in Python |
| `P/session_manager.mu` | generated artifact from `.mu.in` | disappears — no `configure_file` step in a `.py` port |
| `P/Composite_edit_mode.mu` | Composite editor (F1) | → `.py` |
| `P/FolderGroup_edit_mode.mu` | Folder editor (F2) | → `.py` |
| `P/LayoutGroup_edit_mode.mu` | Layout editor (F3) | → `.py` |
| `P/RetimeGroup_edit_mode.mu` | Retime editor (F4) | → `.py` |
| `P/SequenceGroup_edit_mode.mu` | Sequence editor (F5) | → `.py` |
| `P/SourceGroup_edit_mode.mu` | Source cut editor (F6) | → `.py` |
| `P/Stack_edit_mode.mu` | Stack editor (F7) | → `.py` |
| `P/StackGroup_edit_mode.mu` | StackGroup coordinator (F8) | → `.py` |
| `P/Switch_edit_mode.mu` | Switch editor (F9) | → `.py` |
| `P/SwitchGroup_edit_mode.mu` | SwitchGroup coordinator (F10) | → `.py` |
| `P/transform_manip.mu` | pointer transform manipulator (F11) | → `.py`; uses pointer/stylus events |

### O.2 Python files to CREATE

One `.py` per Mu module above (e.g. `session_manager.py`, `composite_edit_mode.py`, …),
or a package subdir. Each a `rv.rvtypes.MinorMode`. **Mode names, menu paths, shortcuts,
and event names MUST be preserved** (external code keys on them — see O.5).

### O.3 Files to MODIFY

| File | Change |
|---|---|
| `P/PACKAGE` | `modes:` entries change `file: <name>` from `.mu` to `.py` for every ported mode (12 entries). Keep `menu`/`shortcut`/`event`/`load` values. `local_thumbnail_gen.py` entry unchanged. |
| `P/CMakeLists.txt` | Remove `CONFIGURE_FILE(session_manager.mu.in …)` and the `MU_QT_*` token vars (11-27). `RV_STAGE(RVPKG)` glob still packages the dir; verify `.py` files stage into `plugins/Python`-side of the rvpkg as expected. |

### O.4 Files REUSED UNCHANGED (do not re-author)

| File(s) | Why unchanged |
|---|---|
| `P/*.ui` (11 files: `session_manager.ui`, `new_node.ui`, `create_image_dialog.ui`, `composite/folder/layout/retime/sequence/source/stack/switch.ui`) | Loaded at runtime via `QUiLoader` in Python exactly as `loadUIFile` did (M1/M2). |
| `P/local_thumbnail_gen.py` | Already Python; a separate `load: immediate` mode. May migrate independently or stay. |
| `P/fallback_thumbnail.png` | Loaded from package dir via support-path (H4). |
| `P/*_48x48.png`, `P/*_out.png`, `P/{channel,layer,view,out}.png` | Source images; runtime icons resolve from the global qrc (below). Still globbed into the rvpkg. |
| `src/lib/app/RvCommon/qrc/RvCommon.qrc` | **The icons are here, not in the package.** `:images/*.png` (add/foldr/playlist/shuffle/home/… and `fallback`) compile into the RvCommon lib and are reachable from PySide via the same `:images/…` paths — **no new qrc needed** (M3). |
| `P/makepng`, `P/maketif` | Dev-only icon regen scripts (shell out to `rvio_hw`); not runtime. |

### O.5 External couplings to FIX (outside the package) ⚠️

| File | Coupling | Action |
|---|---|---|
| `src/plugins/rv-packages/maya_tools/maya_tools.mu(.in)` | `require session_manager;` (:16) + `session_manager.theMode().selectedNodes()` (:159,162,216,218,225,227,264,266) | **BREAKS** — Mu cannot `require` a Python module. |
| `src/plugins/rv-packages/rvnuke/rvnuke_mode.mu(.in)` | `require session_manager;` (:16) + `session_manager.theMode().selectedNodes()` (:411,414,1705,1707,2135,2137,2231,2233,2290,2292,2304,2306,2313,2315,2326,2328) | **BREAKS** — same reason. |
| `src/lib/app/mu_rvui/rvui.mu` (:6715-6722) | reads `Tools/show_session_manager`, `mmm.activateMode("session_manager", true)` | Keyed on **mode name** → no change *if the Python mode keeps the name* `session_manager`. Verify. |
| `src/lib/app/mu_rvui/mode_manager.mu` (:225,448,450) | category gating on `entry.name == "session_manager"` | Keyed on **mode name** → no change if name preserved. Verify. |

> **Cross-language API contract.** `theMode().selectedNodes()` is a Mu-to-Mu call from
> `maya_tools` and `rvnuke`. Porting `session_manager` to Python severs it. Options, in
> order of preference:
>
> 1. Expose `selectedNodes()` as a registered **command** (or internal event) callable
>    from both Mu and Python, and update the two callers to use it.
> 2. Keep a thin Mu shim module named `session_manager` exposing
>    `theMode().selectedNodes()` that forwards to the Python mode via the bridge.
> 3. Migrate `maya_tools` and `rvnuke` too (larger scope).
>
> Whichever is chosen, **`selectedNodes()` must stay callable by Mu consumers** — add a
> golden/integration check for it before removing the Mu module.

### O.6 Coexistence during migration

Both Mu and Python sources can remain in the package directory during the port.
Select which mode(s) RV loads at launch via `RV_MODE_IMPL_<modeName>` or
`RV_PREFER_PYTHON_MODES` — see
**[`../VERIFICATION.md`](../VERIFICATION.md#mupython-implementation-toggle)**.
The `.rvpkg` mechanism is language-agnostic, so both can coexist in the tree while
goldens are captured from Mu and re-run against Python.

---

## Dropped (no equivalent golden test)

Behaviors with no deterministic graph/pixel outcome and no command equivalent were
removed from the tables rather than tracked, so every row above is ✅ or 🟡. Dropped:
modal dialogs (New-Node / Create-Image dialogs — their *outcomes* are pinned by the
create/folder/delete/rename scenarios; the New Viewable / New Folder / Config **toolbar
submenus** are no longer dropped, see C1/C8/I10 and `sm_button_add_menu`/
`sm_button_folder_menu`/`sm_button_config_menu`); settings persistence (`showOnStartup`,
`previewsEnabled`, `show_session_manager`, `General/fps` — not in the session dump; I10
pins the popup's pixel appearance but not the persisted value); and event-sent / timing
checks (`load-ui` sent, progressive-loading suppression). Async live previews
(thumbnail/filmstrip render + `preview-available`) are no longer dropped either — see
§H (H1/H2/H5) and `sm_media_load`. The port still implements the remaining dropped items;
they're verified by inspection, not golden.

## Backlog

Mu baselines for the real-media/real-button scenarios (`sm_media_*`, `sm_button_*`,
`sm_mp4_load`) are captured under `golden/<id>/`. The required migration gates on Linux are
`run_all_goldens.sh` (47 scenarios as of 2026-07-23, headless Xvfb+software-Mesa, hard
pass/fail) **and** `run_gui_sanity_gate.sh` (same scenarios, real display; behavioral is
hard, pixel differences are reported for review rather than gated at a threshold) — see
`../VERIFICATION.md#gui-sanity-gate-real-display`. On macOS, `run_all_goldens_mac.sh` is the
required gate against a separate, Mac-native baseline set in `golden-mac/<id>/` (captured
via `capture_golden_mac.sh`, hard pass/fail on both behavioral and pixel) — see
`../VERIFICATION.md#mac-native-gate`. Optional integration:
`fixtures/run_mp4_integration.sh` + `SM_TEST_MP4_DIR` for `sm_mp4_all`.

Real-media fixtures live in `fixtures/` (regenerate via `fixtures/regenerate_fixtures.sh`,
overridable per-scenario with `SM_TEST_IMAGE_FIXTURE`/`SM_TEST_MOVIE_FIXTURE`). MP4
integration: set `SM_TEST_MP4_DIR` to a directory of clips and run
`fixtures/run_mp4_integration.sh` (`sm_mp4_all` only). Beyond
this, every other golden-gateable behavior has a committed baseline (tables above); the
rest are listed under [Dropped](#dropped-no-equivalent-golden-test). New scenarios, if
needed, go under `scenarios/` with a golden under `golden/<id>/`.

---

## Definition of done

See the shared
**[`../VERIFICATION.md`](../VERIFICATION.md#definition-of-done-per-migration-slice)**: a
slice is accepted when every coverage item in it is ✅ against the Mu goldens at
`-dmax 0`, and any cross-package API it exposes (e.g. `selectedNodes()`, §O.5) stays
callable before the Mu source is removed.
