"""Scenario: session_manager prev/next view navigation.

Covers COVERAGE.md D4 (Prev/Next nav -> previous/nextViewNode).

From a fresh session:
  * add two media-free smptebars movieproc sources
  * resolve each created source's RVSourceGroup via nodeGroup(sourceNode)
  * build three view nodes over both source groups: RVSequenceGroup,
    RVStackGroup, RVLayoutGroup
  * set an explicit starting view (the first-built sequence) so navigation is
    deterministic and non-nil, then:
      setViewNode(nextViewNode())      -- advance one view
      setViewNode(previousViewNode())  -- step back one view

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

# Three view nodes over both source groups.
views = []
for t in ["RVSequenceGroup", "RVStackGroup", "RVLayoutGroup"]:
    n = rvc.newNode(t, "")
    rvc.setNodeInputs(n, src_groups)
    views.append(n)
    log("built view:", n, "type=", rvc.nodeType(n))

log("viewNodes():", rvc.viewNodes())

# --- 2. Navigate with prev/next -----------------------------------------------
# prev/nextViewNode() walk the *view history* (browser back/forward), not the
# viewNodes() list. Seed the history by visiting the three built views in order,
# then step back one so a forward step exists, then exercise the prescribed
# next-then-previous pair. Guard against nil (history endpoints).
for v in views:
    rvc.setViewNode(v)
    pump(50)
log("history seeded; current:", rvc.viewNode())

back = rvc.previousViewNode()
log("previousViewNode() (reposition):", back)
if back is not None:
    rvc.setViewNode(back)
    pump(50)
log("repositioned; current:", rvc.viewNode())

nxt = rvc.nextViewNode()
log("nextViewNode():", nxt)
if nxt is not None:
    rvc.setViewNode(nxt)
    pump(50)
log("after next -> current:", rvc.viewNode())

prv = rvc.previousViewNode()
log("previousViewNode():", prv)
if prv is not None:
    rvc.setViewNode(prv)
    pump(50)
log("after previous -> current:", rvc.viewNode())

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
