#
# Shared helpers for session_manager golden scenarios (package-specific).
#
# Package-agnostic Qt plumbing (pump/click/grab) lives in
# harness/qt_scenario_utils.py; this module owns facts specific to
# session_manager: the panel's objectName, the real-media fixture paths, and
# the session-manager-get-*-path internal events used to know when a real
# preview has actually arrived (as opposed to the deterministic fallback
# icon every media-free scenario uses).
#
# Selection helpers (find_index_by_text / select_row_by_text) deliberately
# never reach into either implementation's internals (no session_manager.py
# theMode() calls) -- the same scenario file must run unmodified against
# both --impl mu (captures the golden) and --impl python (verifies the
# port), per VERIFICATION.md's method. They instead walk the generic
# QAbstractItemModel by DisplayRole text, which both implementations
# populate identically (the UI name each scenario itself assigns).
#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import os
import time

from qt_scenario_utils import QtWidgets, QtCore, pump, shiboken

PANEL_OBJECT_NAME = "sessionManager"

_HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.abspath(os.path.join(_HERE, "..", "fixtures"))

# Env-var override so ad hoc real-media testing doesn't require editing this
# file; default is the committed, repo-relative fixture (never a
# machine-absolute path -- see the diagnostics this module replaces).
IMAGE_FIXTURE = os.environ.get("SM_TEST_IMAGE_FIXTURE") or os.path.join(
    FIXTURES_DIR, "bars_frame.jpg"
)
MOVIE_FIXTURE = os.environ.get("SM_TEST_MOVIE_FIXTURE") or os.path.join(
    FIXTURES_DIR, "bars_clip.mp4"
)

# Production / multi-clip MP4 suites: set SM_TEST_MP4_DIR to a directory of *.mp4
# clips (see fixtures/run_mp4_integration.sh and fixtures/mp4.env.example).
# SM_TEST_MP4_FIXTURE picks one file; SM_TEST_MP4_QUIESCE=1 enables
# thumbnail/filmstrip quiesce on multi-clip runs (slow -- off by default).
MP4_DIR = os.environ.get("SM_TEST_MP4_DIR", "").strip()
MP4_FIXTURE = os.environ.get("SM_TEST_MP4_FIXTURE", "").strip()
MP4_QUIESCE = os.environ.get("SM_TEST_MP4_QUIESCE", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)


def discover_mp4_clips(directory: str) -> list[str]:
    """Return sorted absolute paths to every *.mp4 directly under ``directory``."""
    if not directory or not os.path.isdir(directory):
        return []
    clips = [
        os.path.join(directory, name)
        for name in sorted(os.listdir(directory))
        if name.lower().endswith(".mp4")
        and os.path.isfile(os.path.join(directory, name))
    ]
    return clips


def resolve_mp4_clips() -> list[str]:
    """All MP4 clips for integration scenarios (requires SM_TEST_MP4_DIR)."""
    clips = discover_mp4_clips(MP4_DIR)
    if not clips and MP4_DIR:
        raise FileNotFoundError(
            "SM_TEST_MP4_DIR=%r has no *.mp4 files" % MP4_DIR
        )
    return clips


def resolve_mp4_fixture() -> str:
    """Single MP4 for golden-style load scenarios."""
    if MP4_FIXTURE and os.path.isfile(MP4_FIXTURE):
        return MP4_FIXTURE
    clips = resolve_mp4_clips() if MP4_DIR else []
    if clips:
        return clips[0]
    if os.path.isfile(MOVIE_FIXTURE):
        return MOVIE_FIXTURE
    raise FileNotFoundError(
        "no MP4 fixture: set SM_TEST_MP4_FIXTURE, SM_TEST_MP4_DIR, "
        "SM_TEST_MOVIE_FIXTURE, or run fixtures/regenerate_fixtures.sh"
    )


# Kept alive at module scope deliberately: a `qtutils.sessionWindow()`
# reference that only lives as a local inside a function goes out of scope
# (and gets garbage-collected) the instant that function returns. Empirically
# on macOS, that GC can cascade into deleting the underlying C++ window (and
# everything findChild() found under it) microseconds later -- a widget
# found and validated inside find_session_panel() could already be dead by
# the very next line in the caller. Holding one persistent reference for the
# scenario's lifetime avoids the whole class of "already deleted" races.
_cached_session_window = None


def _get_session_window():
    global _cached_session_window
    import rv.qtutils as qtutils

    if _cached_session_window is None or not shiboken.isValid(_cached_session_window):
        _cached_session_window = qtutils.sessionWindow()
    return _cached_session_window


def find_session_panel(win=None):
    """Locate the session_manager panel widget, or None.

    Right after the activation toggle, `findChild` can hand back a Python
    wrapper for a C++ widget that gets torn down microseconds later -- treat
    any RuntimeError from touching the result the same as "not found yet"
    rather than letting it escape as a scenario-ending crash.
    """
    try:
        win = win or _get_session_window()
        if win is None or not shiboken.isValid(win):
            return None
        panel = win.findChild(QtWidgets.QWidget, PANEL_OBJECT_NAME)
        if panel is not None and shiboken.isValid(panel):
            return panel
        for dw in win.findChildren(QtWidgets.QDockWidget):
            if shiboken.isValid(dw) and "session" in dw.objectName().lower():
                return dw
    except RuntimeError:
        return None
    return None


def open_session_manager_panel(log=print, retries=6, retry_pump_ms=300):
    """Toggle the panel open (key-down--x) and return it. Raises if not found.

    The panel can be briefly torn down and recreated right after the
    activation toggle (observed empirically: a `findChild` immediately after
    the toggle can return a widget whose underlying C++ object is already
    deleted by the time it's touched) -- re-resolve with a fresh lookup
    rather than trusting the first reference.
    """
    import rv.commands as rvc

    try:
        rvc.sendInternalEvent("key-down--x", "")
    except Exception as exc:
        log("key-down--x raised:", exc)

    for attempt in range(retries):
        pump(retry_pump_ms)
        candidate = find_session_panel()
        if candidate is None:
            log(f"panel lookup attempt {attempt}: not found yet, retrying")
            continue
        try:
            if not candidate.isVisible():
                candidate.show()
            pump(400)
            if not shiboken.isValid(candidate):
                raise RuntimeError("invalidated after show()")
            log("panel found:", candidate.objectName(), candidate.width(), "x", candidate.height())
            return candidate
        except RuntimeError as exc:
            log(f"panel lookup attempt {attempt}: died while using it ({exc}), retrying")
            continue
    raise AssertionError("open_session_manager_panel: panel not found (or never usable)")


def find_view_tree(panel):
    """Locate the main node tree (`_viewTreeView`/`NodeTreeView`).

    `panel.findChild(QtWidgets.QTreeView)` with no name filter is NOT safe:
    editor widgets in the Edit tab (e.g. the composite-function combo in
    `composite.ui`) can use a QTreeView internally as their popup view, and
    a plain first-match findChild can grab that instead of the real tree
    (observed empirically). `_viewTreeView` is built into a placeholder
    container with objectName "treeView" (session_manager.mu.in:3197,3227),
    so scope the search to inside that container specifically.
    """
    base = panel.findChild(QtWidgets.QWidget, "treeView")
    if base is None:
        raise AssertionError("find_view_tree: 'treeView' base container not found")
    tree = base.findChild(QtWidgets.QTreeView)
    if tree is None:
        raise AssertionError("find_view_tree: no QTreeView inside the 'treeView' container")
    return tree


def find_button(panel, name):
    """Find a toolbar QToolButton by objectName, robust to widgets that
    aren't nested under `panel`.

    `prevViewButton`/`nextViewButton` live in a `navPanel` container parented
    directly to the `session_manager` QDockWidget (observed empirically via
    the runtime widget parent chain), NOT under the `sessionManager` content
    widget `panel` refers to -- unlike every other toolbar button, which IS
    nested under `panel`. Try the narrow scope first (matches the common
    case exactly), then fall back to searching from the top-level window.
    """
    button = panel.findChild(QtWidgets.QToolButton, name)
    if button is not None:
        return button
    button = panel.window().findChild(QtWidgets.QToolButton, name)
    if button is None:
        raise AssertionError(f"find_button: no QToolButton named {name!r} found")
    return button


def _wait_load_total(log, timeout_ms, poll_ms, label=""):
    import rv.commands as rvc

    deadline = time.time() + timeout_ms / 1000.0
    while rvc.loadTotal() > 0 and time.time() < deadline:
        pump(poll_ms)
    if rvc.loadTotal() > 0:
        raise RuntimeError(
            "loadTotal still %s after %sms%s"
            % (rvc.loadTotal(), timeout_ms, (" (%s)" % label if label else ""))
        )


def _collect_source_nodes():
    """All file/image source leaf nodes currently in the graph."""
    import rv.commands as rvc

    nodes: list[str] = []
    for typ in ("RVFileSource", "RVImageSource"):
        nodes.extend(rvc.nodesOfType(typ))
    return sorted(set(nodes))


def add_sources_explicit(
    paths,
    log=print,
    timeout_ms=120000,
    poll_ms=200,
    tag="explicit",
):
    """Load via ``addSources()`` -- same API as File→Open and drag-drop.

    Unlike ``addSourceVerbose``, this exercises progressive loading
    (``loadTotal`` / ``waitForProgressiveLoading`` / ``after-progressive-loading``),
    which is the path interactive RV uses.

    Returns (source_nodes, group_nodes).  Raises on timeout or if fewer
    sources appear in the graph than paths requested.
    """
    import rv.commands as rvc

    before = set(_collect_source_nodes())
    log("addSources tag=%r paths=%r" % (tag, list(paths)))
    rvc.addSources(list(paths), tag, False, False)
    log(
        "queued loadTotal=%s loadCount=%s"
        % (rvc.loadTotal(), rvc.loadCount())
    )

    try:
        rvc.waitForProgressiveLoading()
    except Exception as exc:
        log("waitForProgressiveLoading:", type(exc).__name__, exc)
        _wait_load_total(log, timeout_ms, poll_ms, label="addSources")

    if rvc.loadTotal() > 0:
        raise RuntimeError(
            "addSources: loadTotal still %s after %sms"
            % (rvc.loadTotal(), timeout_ms)
        )

    source_nodes = sorted(set(_collect_source_nodes()) - before)
    if len(source_nodes) < len(paths):
        raise RuntimeError(
            "addSources: expected %d new sources, got %d (%s)"
            % (len(paths), len(source_nodes), source_nodes)
        )

    group_nodes = [rvc.nodeGroup(n) for n in source_nodes]
    log("loaded source_nodes:", source_nodes)
    log("group nodes:", group_nodes)
    return source_nodes, group_nodes


def add_real_sources(paths, log=print, timeout_ms=15000, poll_ms=200):
    """addSourceVerbose each path, wait for progressive loading to finish.

    Returns (source_nodes, group_nodes) -- source_nodes are the raw
    "..._source" nodes session-manager-get-*-path expects; group_nodes are
    their containing RVSourceGroup nodes, for wiring into stacks/inputs.
    Raises on load timeout rather than silently proceeding with a partially
    loaded source.
    """
    import rv.commands as rvc

    source_nodes = [rvc.addSourceVerbose([p]) for p in paths]
    log("addSourceVerbose:", list(zip(paths, source_nodes)))

    _wait_load_total(log, timeout_ms, poll_ms)
    group_nodes = [rvc.nodeGroup(n) for n in source_nodes]
    log("group nodes:", group_nodes)
    return source_nodes, group_nodes


def add_mp4_clips_sequential(
    clips,
    log=print,
    timeout_ms_per_clip=120000,
    poll_ms=200,
):
    """Load many MP4s one at a time; verify each before continuing.

    Returns (source_nodes, group_nodes).  Use for large clip directories
    (e.g. large clip directories) where a single batch wait is unreliable.
    """
    import rv.commands as rvc

    source_nodes: list[str] = []
    failures: list[tuple[str, str]] = []

    for index, path in enumerate(clips, start=1):
        log("loading clip %d/%d: %s" % (index, len(clips), path))
        try:
            node = rvc.addSourceVerbose([path])
            _wait_load_total(log, timeout_ms_per_clip, poll_ms, label=path)
            movie = rvc.getStringProperty("%s.media.movie" % node)
            if not movie:
                raise RuntimeError("media.movie empty after load")
            source_nodes.append(node)
            log("  OK:", node, "frames:", rvc.sourceMediaInfo(node))
        except Exception as exc:
            failures.append((path, "%s: %s" % (type(exc).__name__, exc)))
            log("  FAILED:", failures[-1][1])

    if failures:
        raise RuntimeError(
            "add_mp4_clips_sequential: %d/%d clips failed: %s"
            % (len(failures), len(clips), failures[:5])
        )

    group_nodes = [rvc.nodeGroup(n) for n in source_nodes]
    log("loaded %d clips, %d source groups" % (len(source_nodes), len(group_nodes)))
    return source_nodes, group_nodes


def quiesce_real_previews(source_nodes, timeout_ms=20000, poll_ms=250, log=print):
    """Block until every source node has a real thumbnail AND filmstrip on disk.

    This is the fix for COVERAGE.md H1/H2/H5 (previously "Dropped" as
    non-deterministic): rather than a growing best-effort sleep, poll the
    exact same paths session_manager itself treats as "preview ready"
    (session-manager-get-thumbnail-path / -filmstrip-path), and raise if
    they never arrive -- a capture must never proceed on an unquiesced,
    nondeterministic panel.

    Call this BEFORE `rv.extra_commands.setUIName` on these nodes: a real
    source's ui.name gets auto-set to its media basename once its source
    group actually finishes completing (asynchronously, observed to land
    slightly after `loadTotal()` reaches 0), which can silently clobber a
    name set too early. Naming after quiescing avoids the race.
    """
    import rv.commands as rvc

    deadline = time.time() + timeout_ms / 1000.0
    pending = set(source_nodes)
    while pending and time.time() < deadline:
        pump(poll_ms)
        for n in list(pending):
            try:
                thumb = rvc.sendInternalEvent("session-manager-get-thumbnail-path", n)
                strip = rvc.sendInternalEvent("session-manager-get-filmstrip-path", n)
            except Exception as exc:
                log("quiesce probe failed for", n, exc)
                continue
            if thumb and os.path.isfile(thumb) and strip and os.path.isfile(strip):
                pending.discard(n)
    if pending:
        raise RuntimeError(f"quiesce_real_previews: TIMEOUT for nodes: {sorted(pending)}")
    log("previews quiesced for:", sorted(source_nodes))


def find_tab(panel, title, settle_ms=200):
    """Switch the panel's QTabWidget to the tab titled ``title``; return it."""
    tab_widget = panel.findChild(QtWidgets.QTabWidget, "tabWidget")
    if tab_widget is None:
        raise AssertionError("find_tab: tabWidget not found")
    for i in range(tab_widget.count()):
        if tab_widget.tabText(i) == title:
            tab_widget.setCurrentIndex(i)
            pump(settle_ms)
            return tab_widget
    raise AssertionError(f"find_tab: no tab titled {title!r} (has: "
                          f"{[tab_widget.tabText(i) for i in range(tab_widget.count())]})")


# The node-name role session_manager stores on every tree/inputs-list item
# (session_manager.mu.in:1944 `item.setData(QVariant(node), Qt.UserRole + 2)`,
# :1509 same for the Inputs list). Prefer this over DisplayRole for finding a
# SPECIFIC node's row: source rows' display text is blanked once previews are
# enabled (:1512-1516 Inputs list; the main tree does the same once a preview
# widget attaches -- observed empirically, timing-dependent), and a rename
# via `extra_commands.setUIName` never reaches an already-built row's display
# text either (no rebuild is triggered for a plain property write on an
# existing node). The node-name role is unaffected by either: scenarios
# already have the exact node name as a Python variable (from `newNode`/
# `add_real_sources`), so match on that instead of display text.
NODE_NAME_ROLE = QtCore.Qt.UserRole + 2


def _walk_for_role(model, parent, role, value):
    for row in range(model.rowCount(parent)):
        idx = model.index(row, 0, parent)
        if idx.data(role) == value:
            return idx
        found = _walk_for_role(model, idx, role, value)
        if found is not None:
            return found
    return None


def _walk_for_text(model, parent, text):
    return _walk_for_role(model, parent, QtCore.Qt.DisplayRole, text)


def _collect_all_text(model, parent=None):
    out = []
    for row in range(model.rowCount(parent if parent is not None else QtCore.QModelIndex())):
        idx = model.index(row, 0, parent if parent is not None else QtCore.QModelIndex())
        out.append(idx.data(QtCore.Qt.DisplayRole))
        out.extend(_collect_all_text(model, idx))
    return out


def find_index_by_text(view, text):
    """Walk ``view``'s model (recursively, so this works for tree or flat
    list views alike) for the first row whose DisplayRole matches ``text``.
    """
    model = view.model()
    if model is None:
        raise AssertionError("find_index_by_text: view has no model")
    index = _walk_for_text(model, QtCore.QModelIndex(), text)
    if index is None:
        raise AssertionError(
            f"find_index_by_text: no row with text {text!r}; rows seen: {_collect_all_text(model)}"
        )
    return index


def find_child_index_by_text(view, parent_index, text):
    """Like ``find_index_by_text``, but only searches descendants of
    ``parent_index`` -- needed when the same node appears under more than
    one tree parent (e.g. a source shared by two folders) and the specific
    occurrence matters (COVERAGE §I8 multi-parent branch).
    """
    model = view.model()
    if model is None:
        raise AssertionError("find_child_index_by_text: view has no model")
    index = _walk_for_text(model, parent_index, text)
    if index is None:
        raise AssertionError(
            f"find_child_index_by_text: no row with text {text!r} under given parent"
        )
    return index


def find_index_by_node(view, node_name):
    """Walk ``view``'s model for the row whose node-name role matches
    ``node_name`` exactly -- the preferred way to find a specific node's
    row (see NODE_NAME_ROLE)."""
    model = view.model()
    if model is None:
        raise AssertionError("find_index_by_node: view has no model")
    index = _walk_for_role(model, QtCore.QModelIndex(), NODE_NAME_ROLE, node_name)
    if index is None:
        raise AssertionError(f"find_index_by_node: no row for node {node_name!r}")
    return index


def find_child_index_by_node(view, parent_index, node_name):
    """Like ``find_index_by_node``, scoped to descendants of ``parent_index``
    -- needed when the same node appears under more than one tree parent
    (e.g. a source shared by two folders) and the specific occurrence
    matters (COVERAGE §I8 multi-parent branch)."""
    model = view.model()
    if model is None:
        raise AssertionError("find_child_index_by_node: view has no model")
    index = _walk_for_role(model, parent_index, NODE_NAME_ROLE, node_name)
    if index is None:
        raise AssertionError(f"find_child_index_by_node: no row for node {node_name!r} under given parent")
    return index


def select_row_by_node(view, node_name, extend=False):
    index = find_index_by_node(view, node_name)
    select_index(view, index, extend=extend)
    return index


def select_index(view, index, settle_ms=150, extend=False):
    """Select ``index`` in ``view``. ``extend=True`` adds to the current
    selection instead of replacing it (for multi-select scenarios).

    Uses the selection model's own `setCurrentIndex(index, flags)` (not the
    view's plain `setCurrentIndex`, then a separate `.select()` call): doing
    it in two steps let the view's default current-index behavior clear a
    prior extend=True selection before or after `.select()` ran (observed
    empirically -- a second extend=True call was silently losing the first
    row's selection).
    """
    flags = QtCore.QItemSelectionModel.Rows | (
        QtCore.QItemSelectionModel.Select if extend else QtCore.QItemSelectionModel.ClearAndSelect
    )
    view.selectionModel().setCurrentIndex(index, flags)
    pump(settle_ms)


def select_row_by_text(view, text, extend=False):
    index = find_index_by_text(view, text)
    select_index(view, index, extend=extend)
    return index


def select_row_by_position(view, row, extend=False):
    """Select the top-level row at ``row`` by position rather than text.

    Needed for the Inputs-tab list specifically: `updateInputs`
    (session_manager.mu.in:1486-1522) BLANKS a source row's display text
    (`item.setText("")`) whenever previews are enabled, replacing it with a
    custom preview widget -- so `find_index_by_text`/`select_row_by_text`
    can never match a real-media source row there by name. Scenarios that
    build the Inputs list themselves already know the exact order, so
    selecting by position sidesteps the blanked-text problem entirely.
    """
    model = view.model()
    if model is None:
        raise AssertionError("select_row_by_position: view has no model")
    index = model.index(row, 0, QtCore.QModelIndex())
    if not index.isValid():
        raise AssertionError(f"select_row_by_position: row {row} is not valid")
    select_index(view, index, extend=extend)
    return index
