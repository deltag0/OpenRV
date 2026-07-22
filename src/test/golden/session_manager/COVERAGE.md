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
"verified in the Python port."

### Existing scenarios
| ID | File | What it does |
|---|---|---|
| `default_session` | `scenarios/default_session.py` | Empty session; behavioral only. |
| `tree_readonly` | `scenarios/tree_readonly.py` | 2 `smptebars` sources; opens panel; captures graph + panel PNG. |

---

## A. Activation & panel lifecycle

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| A1 | `x` / `key-down--x` toggles the dock panel visible/hidden | PACKAGE:14 | P | 🟡 | `tree_readonly` (opens only) |
| A2 | Tools ▸ Session Manager menu entry toggles the panel | PACKAGE:13 | P | ⬜ | `sm_activation` |
| A3 | Panel is a left-docked `QDockWidget` titled "Session Manager" | 3195,3278 | P | 🟡 | `tree_readonly` |
| A4 | Startup visibility honors `showOnStartup` = yes/no/last | 1279,1305,3480 | B(setting)+P | ⬜ | `sm_startup_pref` |
| A5 | Disabling `sessionmanager_category` auto-toggles the panel off | 1262-1269 | P | ⬜ | `sm_category_gate` |
| A6 | Quitting/session-deletion sets `_quitting`, suppresses work | 1250-1260 | — | ⬜ | (lifecycle) |

## B. Tree view — structure & display

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| B1 | Nodes bucketed into FOLDERS/SOURCES/SEQUENCES/STACKS/LAYOUTS/OTHER headers | 2133-2179 | B+P | ✅ | `tree_readonly` |
| B2 | Category headers non-selectable, styled, size-hinted | 2144-2152 | P | ✅ | `tree_readonly` |
| B3 | Per-node type icon (`iconForNode`) | 3303-3314 | P | ✅ | `tree_readonly` |
| B4 | Current-view node marked with "✔" in status column | 1323,1585 | P | 🟡 | `tree_readonly` |
| B5 | Categories sorted; rows sorted (`sort(0, Ascending)`) | 2206 | B+P | ✅ | `tree_readonly` |
| B6 | Category expansion persisted via `#Session.sm_view.<CATEGORY>` | 2188-2202 | B | 🟡 | `sm_expansion` |
| B7 | Node expansion persisted (`sm_state.expandState`) | 208-241 | B | ⬜ | `sm_expansion` |
| B8 | Empty categories omitted | 2183 | P | ✅ | `tree_readonly` |
| B9 | Source rows render preview widget when previews enabled | 1850-1923 | P | 🟡 | `tree_readonly` (fallback icon; see §H) |

## C. Node creation (Add / Folder / dialogs)

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| C1 | Add ▸ Sequence/Stack/Switch/Folder/Layout/Retime create the right node type | 3348-3353,3382-3387 | B+P | ⬜ | `sm_create_views` |
| C2 | Add ▸ Color / OCIO / Dynamic (Dynamic gated by `RV_ENABLE_DYNAMIC_NODE`) | 3365-3370 | B | ⬜ | `sm_create_nodes` |
| C3 | Selected nodes become inputs of the new node; auto-named (`renameByType`) | 2522-2538,2281-2314 | B | ⬜ | `sm_create_views` |
| C4 | New Node by Type… dialog (combo from `nodeTypes(true)`) creates chosen type | 2540-2562 | B+P(dialog) | ⬜ | `sm_new_node_dialog` |
| C5 | Create Image dialog: SRGB/ACES charts, color bars, black, color, blank → movieproc source | 2564-2681 | B+P(dialog) | ⬜ | `sm_create_image` |
| C6 | Create Image dialog field logic (size/fps/length/color per media type) | 2606-2678 | P(dialog) | ⬜ | `sm_create_image` |
| C7 | Color swatch opens `QColorDialog`, live-updates color | 2267-2275,2603 | P | ⬜ | `sm_create_image` |
| C8 | New Folder: empty / from selection (reparent) / from copy | 2699-2753 | B | ⬜ | `sm_folders` |
| C9 | Created group made current via `setViewNode` | 2534,2752 | B | ⬜ | `sm_create_views` |

## D. View switching & navigation

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| D1 | Double-click tree node → `setViewNode` | 1343-1373 | B | ⬜ | `sm_view_switch` |
| D2 | Single-click top-level selection → becomes current view | 1466-1484 | B | ⬜ | `sm_view_switch` |
| D3 | Status-column click views a sub-component (`setImageRequest`) | 1375-1389,530 | B | ⬜ | `sm_subcomponents` |
| D4 | Prev/Next nav buttons → `previous/nextViewNode` | 3085-3101 | B+P | ⬜ | `sm_nav` |
| D5 | Nav buttons enabled only when prev/next exists; `viewLabel` shows current UI name | 1565-1574 | P | ⬜ | `sm_nav` |
| D6 | "Select Current View" (home) selects + scrolls to current node | 1536-1563 | P | ⬜ | `sm_nav` |
| D7 | `after/before-graph-view-change` keep tree ✔, nav, tab, edit-UI in sync | 1576-1637 | B+P | ⬜ | `sm_view_switch` |

## E. Inputs tab

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| E1 | Inputs list reflects `nodeConnections` of the current view node | 1486-1534 | B+P | ⬜ | `sm_inputs` |
| E2 | Double-click input → view it | 3532 | B | ⬜ | `sm_inputs` |
| E3 | Reorder up/down → `setInputs` new order | 2806-2860 | B | ⬜ | `sm_inputs_reorder` |
| E4 | Sort A-Z / Z-A → `setInputs` sorted (folders also `setSortKeyInParent`) | 2871-2930 | B | ⬜ | `sm_inputs_sort` |
| E5 | Delete input → `setInputs` minus selection | 3022-3052 | B | ⬜ | `sm_inputs` |
| E6 | Inputs list disabled for source-type view nodes | 1594-1597 | P | ⬜ | `sm_inputs` |
| E7 | Model row insert/remove (drag reorder) → `rebuildInputsFromList` → `setInputs` | 3515-3517,2932-2989 | B | ⬜ | `sm_inputs_reorder` |

## F. Edit tab & per-view edit modes

The Edit tab hosts editors contributed by sibling modes via the `session-manager-load-ui`
event. Each edit mode writes specific `#RV*` properties. **All B-gate** (property writes),
plus **P** for the editor widget rendering.

| # | Edit mode | Properties written | Ref | Status | Scenario |
|---|---|---|---|---|---|
| F1 | Composite | `#RVStack.composite.type`, `.dissolveAmount` | Composite_edit_mode.mu:49,76 | ⬜ | `sm_edit_composite` |
| F2 | FolderGroup | `#RVFolderGroup.mode.viewType` (+ swaps child modes) | FolderGroup_edit_mode.mu:52 | ⬜ | `sm_edit_folder` |
| F3 | LayoutGroup | `#RVLayoutGroup.layout.mode/.spacing/.gridRows/.gridColumns` | LayoutGroup_edit_mode.mu:54-67 | ⬜ | `sm_edit_layout` |
| F4 | RetimeGroup | `#RVRetime.visual/audio.scale/offset`, `.output.fps` | RetimeGroup_edit_mode.mu:39-195 | ⬜ | `sm_edit_retime` |
| F5 | SequenceGroup | `#RVSequence.mode.autoEDL/useCutInfo`, `.output.fps/size`, `#RVSequenceGroup.timing.retimeInputs` | SequenceGroup_edit_mode.mu:94-214 | ⬜ | `sm_edit_sequence` |
| F6 | SourceGroup | `#RVFileSource.cut.in/out/syncGui` (+ `setInPoint/OutPoint`) | SourceGroup_edit_mode.mu:55-149 | ⬜ | `sm_edit_source` |
| F7 | Stack | `#RVStack.mode.*`, `.output.chosenAudioInput/fps/size`, `#View.timing.retimeInputs` | Stack_edit_mode.mu:186-328 | ⬜ | `sm_edit_stack` |
| F8 | StackGroup | activates Composite+Stack; wipes from `<view>.ui.wipes` | StackGroup_edit_mode.mu:40-105 | ⬜ | `sm_edit_stackgroup` |
| F9 | Switch | `#RVSwitch.mode.*`, `.output.input/size/autoSize` | Switch_edit_mode.mu:141-220 | ⬜ | `sm_edit_switch` |
| F10 | SwitchGroup | (activates Switch_edit_mode only) | SwitchGroup_edit_mode.mu | ⬜ | `sm_edit_switchgroup` |
| F11 | transform_manip | `<tform>.transform.translate/scale/rotate`, `.tag.tmanip*` | transform_manip.mu:240-362 | ⬜ | `sm_transform_manip` |
| F12 | `session-manager-load-ui` sent on view-change/activate/edit-mode-activated/reload | 1247,1294,1599,1628 | ⬜ | `sm_edit_loadui` |
| F13 | Per-node tab selection persisted (`sm_state.tab`); source groups default to Edit tab | 3054-3076 | ⬜ | `sm_tabs` |

## G. Drag & drop  ⚠️ highest-risk port area

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| G1 | Tree drag reparent — MoveAction: `addInput(new)` + `removeInput(old)` | 1391-1448 | B | ⬜ | `sm_dnd_reparent` |
| G2 | Tree drag — CopyAction: `addInput` only (no removal) | 1409 | B | ⬜ | `sm_dnd_copy` |
| G3 | `dragEnterEvent` disables drop on FOLDERS root when dragging non-folders | 869-918 | B(neg) | ⬜ | `sm_dnd_guards` |
| G4 | `dragMoveEvent` rejects: non-col-0, drop-on-self, existing-sibling-reorder | 920-975 | B(neg) | ⬜ | `sm_dnd_guards` |
| G5 | `dropEvent` defers folder re-sort via `_sortTimer` (100/200ms) → `setSortKeyInParent` | 977-998,482 | B | ⬜ | `sm_dnd_reparent` |
| G6 | `NodeModel.mimeData` exports `rvnode://RVID/TYPE/NODE[/media]` URLs | 746-797 | B(mime) | ⬜ | `sm_dnd_mime` |
| G7 | Drag tree→Inputs forces CopyAction (adds as input) | 1022-1031 | B | ⬜ | `sm_inputs_dnd` |
| G8 | Post-drop tree refresh via `_dropTimer` | 1033-1041 | B | ⬜ | `sm_inputs_dnd` |

> DnD needs **synthetic Qt input events** (`QTest`) — command-API driving can't reach it.
> This is the one slice that requires Option-2 driving; schedule it last.

## H. Source previews / thumbnails / filmstrip  ⚠️ nondeterminism

Provided by `local_thumbnail_gen.py` (a separate `load: immediate` Python mode) via
`rvio` subprocesses, communicated over internal events. **Async and timing-dependent.**

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| H1 | Thumbnail = source midpoint frame via `rvio -t <mid>` | local_thumbnail_gen.py:214 | P | ⬜ | `sm_previews` |
| H2 | Filmstrip = up to 25 frames, `rvio` over a temp layout session | :281-427 | P | ⬜ | `sm_previews` |
| H3 | Hover swaps thumbnail↔filmstrip; scrub shows frame under cursor | 651-726 | P | ⬜ | `sm_preview_hover` |
| H4 | Fallback `fallback_thumbnail.png` until real preview arrives | 3322,1867 | P | ✅ | `tree_readonly` |
| H5 | `session-manager-preview-available` → drop cache, rebuild row | 2225-2251 | P | ⬜ | `sm_previews` |
| H6 | Previews suspended during playback/loading; env `RV_SESSION_MANAGER_USE_THUMBNAILS=0` disables | :157-160,3158 | P | ⬜ | `sm_previews_off` |

> **Determinism rule:** default pilot fixtures use media-free sources and capture with
> the fallback icon (H4), which is deterministic. Real-preview scenarios (H1/H2/H5) must
> either quiesce on `session-manager-preview-available` for every source before grabbing,
> or crop the preview column out of the PNG before diffing.

## I. Toolbar buttons & context menus

| # | Behavior | Ref | Gate | Status | Scenario |
|---|---|---|---|---|---|
| I1 | Button bar: Create View / Folder / Delete / Edit Info / Configure / Select Current | 3280-3345 | P | 🟡 | `tree_readonly` (rendered) |
| I2 | Inputs side buttons: up/down/A-Z/Z-A/delete | 3285-3341 | P | ⬜ | `sm_inputs` |
| I3 | "New Viewable" popup menu contents & actions | 3347-3438 | P+B | ⬜ | `sm_create_views` |
| I4 | "New Folder" popup menu (3 items) | 3440-3449 | P+B | ⬜ | `sm_folders` |
| I5 | "Config" popup: startup radio group + Show Source Previews toggle | 3451-3474 | P+B(setting) | ⬜ | `sm_config_menu` |
| I6 | Tree right-click context menu (New Folder/New Viewable submenus + delete/edit/select) | 1723-1738 | P+B | ⬜ | `sm_context_menu` |
| I7 | Inline rename (Edit key / Edit Info button) → `setUIName` | 1449-1463,2798 | B | ⬜ | `sm_rename` |
| I8 | Delete View: `removeInput` if multi-parent folder child, else `deleteNode` | 2755-2784 | B | ⬜ | `sm_delete` |

## J. Settings, persistence & private properties

| # | Behavior | Ref | Gate | Status |
|---|---|---|---|---|
| J1 | `SessionManager/showOnStartup` (yes/no/last, default no) | 1279,3128 | B(setting) | ⬜ |
| J2 | `SessionManager/previewsEnabled` (default true) | 3136,3166 | B(setting) | ⬜ |
| J3 | `Tools/show_session_manager` mirrors visibility | 1283,3129 | B(setting) | ⬜ |
| J4 | `General/fps` seeds Create Image FPS | 2580 | — | ⬜ |
| J5 | Per-node `sm_state.tab/sortKey/sortKeyParent/expandState/expandedSubState/toolTip` | 168-332,3056 | B | ⬜ |
| J6 | `sm_state.componentOfNode/componentHash/componentSubType/componentFolderOfNode` | 2325-2388 | B | ⬜ |
| J7 | `#Session.sm_view.<CATEGORY>`, `#Session.sm_window.splitter` | 2188,1203 | B | 🟡 |
| J8 | `<source>.request.imageComponent` (sub-component selection) | 519-606 | B | ⬜ |

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
| K2 | `after-clear-session` rebuilds empty tree | B+P | ⬜ | `sm_clear` |
| K3 | Progressive-loading window suppresses tree updates, then one rebuild | B | ⬜ | `sm_progressive` |
| K4 | `graph-node-inputs-changed` updates inputs of current view | B | ⬜ | `sm_inputs` |
| K5 | `session-manager-load-ui` emitted on the correct transitions | B(event) | ⬜ | `sm_edit_loadui` |

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

## Scenario backlog

Ordered roughly by value and by driving mechanism. Scenarios `sm_*` are to be written
under `scenarios/`, each producing `session.rv` (+ `panel.png` where a P gate applies)
and a committed golden under `golden/<id>/`.

**Command-API driven (Option 1 — build first):**
`sm_activation`, `sm_startup_pref`, `sm_create_views`, `sm_create_nodes`, `sm_folders`,
`sm_view_switch`, `sm_nav`, `sm_inputs`, `sm_inputs_reorder`, `sm_inputs_sort`,
`sm_subcomponents`, `sm_rename`, `sm_delete`, `sm_clear`, `sm_progressive`,
`sm_expansion`, `sm_tabs`, `sm_config_menu`, `sm_edit_composite`, `sm_edit_folder`,
`sm_edit_layout`, `sm_edit_retime`, `sm_edit_sequence`, `sm_edit_source`,
`sm_edit_stack`, `sm_edit_stackgroup`, `sm_edit_switch`, `sm_edit_switchgroup`,
`sm_edit_loadui`, `sm_new_node_dialog`, `sm_create_image`.

**Synthetic-input driven (Option 2 — QTest; schedule last):**
`sm_dnd_reparent`, `sm_dnd_copy`, `sm_dnd_guards`, `sm_dnd_mime`, `sm_inputs_dnd`,
`sm_context_menu`, `sm_preview_hover`, `sm_transform_manip`.

**Preview / nondeterminism (needs quiesce-or-crop):**
`sm_previews`, `sm_previews_off`.

---

## Definition of done

See the shared
**[`../VERIFICATION.md`](../VERIFICATION.md#definition-of-done-per-migration-slice)**: a
slice is accepted when every coverage item in it is ✅ against the Mu goldens at
`-dmax 0`, and any cross-package API it exposes (e.g. `selectedNodes()`, §O.5) stays
callable before the Mu source is removed.
