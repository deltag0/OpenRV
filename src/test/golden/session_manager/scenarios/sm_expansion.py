"""Scenario: tree expansion state persisted (COVERAGE §B6 / §B7 / §J7 / §J5).

The node tree's `expanded`/`collapsed` signals are wired to `setItemExpandedState`
(session_manager.mu:3527-3528, method :1696-1721):
  * expanding/collapsing a CATEGORY header (a row whose text is not a node) writes
    `#Session.sm_view.<CATEGORY>` (IntType) = 1/0                 -> §B6 / §J7
  * expanding/collapsing a NODE row (nodeExists) writes
    `<node>.sm_state.expandState` (StringType) via setExpandedInParent -> §B7 / §J5

This scenario builds a folder containing two sources, opens the panel so the mode builds
the tree, then programmatically expands rows on the node QTreeView with `tv.expand(index)`
(NOT a drag; allowed). Category headers are auto-expanded on build, so to reliably fire
the persistence handler for §B6 we collapse-then-expand each top-level row; we then expand
each folder node row (a child of the FOLDERS category) to fire §B7. After pumping we save.

We pin:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png
"""

import os
import time

import rv.commands as rvc
import rv.extra_commands as rve

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


try:
    from PySide6 import QtWidgets, QtCore
    import shiboken6 as shiboken
except ImportError:  # pragma: no cover - older Qt
    from PySide2 import QtWidgets, QtCore
    import shiboken2 as shiboken

import rv.qtutils as qtutils


def pump(ms):
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


# --- 1. Build a small graph: a folder with two sources -------------------------
children = []
for _ in range(2):
    s = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
    children.append(rvc.nodeGroup(s))
folder = rvc.newNode("RVFolderGroup", "")
rve.setUIName(folder, "MyFolder")
rvc.setNodeInputs(folder, children)
rvc.setViewNode(folder)
log("folder:", folder, "children:", children)

# --- 2. Open the panel so the mode builds the tree -----------------------------
try:
    rvc.sendInternalEvent("key-down--x", "")
except Exception as e:
    log("sendInternalEvent key-down--x raised:", e)
pump(800)

win = qtutils.sessionWindow()
panel = win.findChild(QtWidgets.QWidget, "sessionManager") if win else None
log("sessionWindow:", bool(win), "panel(sessionManager) found:", bool(panel))

# --- 3. Locate the node tree (the QTreeView that is NOT uiTreeWidget) -----------
node_tree = None
if win is not None:
    for tv in win.findChildren(QtWidgets.QTreeView):
        log("  QTreeView objectName:", repr(tv.objectName()))
        if tv.objectName() != "uiTreeWidget":
            node_tree = tv
            break
log("node_tree found:", bool(node_tree))

# --- 4. Drive expansion so the persistence handlers fire -----------------------
if node_tree is not None:
    model = node_tree.model()
    log("model:", bool(model), "top-level rows:", model.rowCount() if model else -1)

    if model is not None:
        # Top-level rows are the category headers -> §B6 (#Session.sm_view.<CATEGORY>).
        # They are auto-expanded on build, so collapse then expand to fire the handler.
        for r in range(model.rowCount()):
            idx = model.index(r, 0)
            label = model.data(idx)
            log("  top-level row", r, "label:", label,
                "hasChildren:", model.hasChildren(idx))
            node_tree.collapse(idx)
            pump(60)
            node_tree.expand(idx)
            pump(60)

        # Descend one level: folder node rows -> §B7 (<node>.sm_state.expandState).
        # Expand every child that itself has children (folder nodes with sources).
        for r in range(model.rowCount()):
            parent_idx = model.index(r, 0)
            for c in range(model.rowCount(parent_idx)):
                child_idx = model.index(c, 0, parent_idx)
                if model.hasChildren(child_idx):
                    log("    expanding child row", c, "under top", r,
                        "label:", model.data(child_idx))
                    # Toggle to guarantee the expanded signal fires.
                    node_tree.collapse(child_idx)
                    pump(60)
                    node_tree.expand(child_idx)
                    pump(60)
    pump(300)

# --- 5. Verify which expansion properties now exist ----------------------------
for cat in ["FOLDERS", "SOURCES", "SEQUENCES", "STACKS", "LAYOUTS", "OTHER"]:
    p = "#Session.sm_view.%s" % cat
    if rvc.propertyExists(p):
        log("sm_view", cat, "=", rvc.getIntProperty(p))
es = "%s.sm_state.expandState" % folder
log("folder expandState exists:", rvc.propertyExists(es),
    (rvc.getStringProperty(es) if rvc.propertyExists(es) else ""))

# --- 6. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 7. Screenshot the panel ---------------------------------------------------
if panel is None:
    for dw in (win.findChildren(QtWidgets.QDockWidget) if win else []):
        if "session" in dw.objectName().lower():
            panel = dw
            break

if panel is not None:
    if not panel.isVisible():
        panel.show()
    pump(400)
    log("panel geometry:", panel.width(), "x", panel.height(), "visible", panel.isVisible())
    pixmap = panel.grab()
    ok = pixmap.save(os.path.join(out_dir, "panel.png"), "PNG")
    log("panel.png saved:", ok, "size", pixmap.width(), "x", pixmap.height())
else:
    log("PANEL NOT FOUND -- no panel.png written")

diag.close()
