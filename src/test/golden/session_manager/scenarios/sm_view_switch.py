"""Scenario: session_manager view switching between nodes.

Covers COVERAGE.md D1/D2/D7 (setViewNode transitions; after/before-graph-view-
change keep tree/nav in sync).

From a fresh session:
  * add two media-free smptebars movieproc sources
  * resolve each created source's RVSourceGroup via nodeGroup(sourceNode)
  * create one RVSequenceGroup over both source groups
  * switch the current view: source group 1 -> the sequence -> source group 2
    (source group 2 is the final view left in the session)

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

# One sequence over both source groups.
seq = rvc.newNode("RVSequenceGroup", "")
rvc.setNodeInputs(seq, src_groups)
log("sequence:", seq, "type=", rvc.nodeType(seq))

# --- 2. Switch the current view: source1 -> sequence -> source2 ----------------
for target in [src_groups[0], seq, src_groups[1]]:
    rvc.setViewNode(target)
    pump(50)
    log("setViewNode", target, "-> current:", rvc.viewNode())

log("final view:", rvc.viewNode())

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
