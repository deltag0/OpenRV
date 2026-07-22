"""Scenario: session_manager creation of all six group/view types.

Covers COVERAGE.md C1/C3/C9 (Add -> Sequence/Stack/Switch/Folder/Layout/Retime
create the right node type; selected nodes become inputs; created group made
current via setViewNode).

From a fresh session:
  * add two media-free smptebars movieproc sources
  * resolve each created source's RVSourceGroup via nodeGroup(sourceNode)
  * create all six group types (RVSequenceGroup, RVStackGroup, RVSwitchGroup,
    RVFolderGroup, RVLayoutGroup, RVRetimeGroup) via newNode(type, "") then
    setNodeInputs(new, [srcGrp1, srcGrp2])
  * leave the last-created node as the current view (setViewNode)

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

Structure mirrors scenarios/tree_readonly.py exactly.
"""

import os
import time

import rv.commands as rvc

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- Qt bindings (Qt6 build -> PySide6; fall back to PySide2) ------------------
try:
    from PySide6 import QtWidgets, QtCore
    import shiboken6 as shiboken
except ImportError:  # pragma: no cover - older Qt
    from PySide2 import QtWidgets, QtCore
    import shiboken2 as shiboken

import rv.qtutils as qtutils


def pump(ms):
    """Pump the Qt event loop for ~ms without a bare sleep."""
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


# --- 1. Build a deterministic, media-free graph --------------------------------
srcs = [
    "smptebars,start=1,end=24,fps=24.movieproc",
    "smptebars,start=1,end=24,fps=24.movieproc",
]
src_groups = []
for s in srcs:
    src_node = rvc.addSourceVerbose([s])
    grp = rvc.nodeGroup(src_node)
    src_groups.append(grp)
    log("added source:", src_node, "group:", grp)

log("source groups:", src_groups)

# --- 2. Create all six group/view types over the two source groups -------------
view_types = [
    "RVSequenceGroup",
    "RVStackGroup",
    "RVSwitchGroup",
    "RVFolderGroup",
    "RVLayoutGroup",
    "RVRetimeGroup",
]
last = None
for t in view_types:
    n = rvc.newNode(t, "")
    # RVRetimeGroup accepts exactly one input (it retimes a single upstream
    # view); setNodeInputs with two inputs raises. Give it a single source
    # group so the type is still created and connected over the fixture.
    inputs = src_groups[:1] if t == "RVRetimeGroup" else src_groups
    rvc.setNodeInputs(n, inputs)
    last = n
    log("created", t, "->", n, "type=", rvc.nodeType(n), "inputs=", inputs)

# Leave the last-created group as the current view.
rvc.setViewNode(last)
log("viewNode set to:", last, "current:", rvc.viewNode())
log("nodes:", rvc.nodes())

# --- 3. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 4. Show the session_manager panel, then screenshot it ---------------------
try:
    rvc.sendInternalEvent("key-down--x", "")
except Exception as e:
    log("sendInternalEvent key-down--x raised:", e)
pump(600)

win = qtutils.sessionWindow()
panel = win.findChild(QtWidgets.QWidget, "sessionManager") if win else None
log("sessionWindow:", bool(win), "panel(sessionManager) found:", bool(panel))

if panel is None:
    for dw in (win.findChildren(QtWidgets.QDockWidget) if win else []):
        log("  dock:", dw.objectName(), "visible", dw.isVisible())
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
