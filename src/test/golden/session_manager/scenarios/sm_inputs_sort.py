"""Scenario: session_manager Inputs tab -- pinned A-Z sorted input order (E4).

Same three-source RVStackGroup as ``sm_inputs``, but each source GROUP node is
given a distinct UI name FIRST (in an order that is NOT alphabetical:
``Cam_C, Cam_A, Cam_B`` for creation order 000000/000001/000002), then the
inputs are wired via setNodeInputs in ALPHABETICAL order of ``ui.name``
(A-Z: Cam_A, Cam_B, Cam_C). Because the naming is deliberately un-sorted, the
resulting connection order (000001, 000002, 000000) is observably the sorted
order rather than creation order -- pinning the A-Z sort behavior.

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

Notes (see harness bring-up / tree_readonly.py):
  * `-pyeval` runs BEFORE QCoreApplication::exec(); pump before grab().
  * Output must go to files; RV redirects stdout to its own log.
  * Connect the GROUP nodes (nodeGroup(src)), not the raw source nodes.
"""

import os
import time

import rv.commands as rvc
import rv.extra_commands as rvec

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
    "smptebars,start=1,end=24,fps=24.movieproc",
]
group_nodes = []
for s in srcs:
    src_node = rvc.addSourceVerbose([s])
    grp = rvc.nodeGroup(src_node)
    group_nodes.append(grp)
log("source group nodes (creation order):", group_nodes)

# --- 2. Name the groups in a deliberately NON-alphabetical order ---------------
# creation order 000000/000001/000002 gets names Cam_C / Cam_A / Cam_B
names = ["Cam_C", "Cam_A", "Cam_B"]
for grp, name in zip(group_nodes, names):
    rvec.setUIName(grp, name)
log("uiNames:", [(g, rvec.uiName(g)) for g in group_nodes])

# --- 3. RVStackGroup wired in A-Z order of ui.name -----------------------------
sorted_groups = sorted(group_nodes, key=lambda g: rvec.uiName(g))
log("A-Z sorted inputs:", [(g, rvec.uiName(g)) for g in sorted_groups])

stack = rvc.newNode("RVStackGroup", "")
log("stack group node:", stack)
rvc.setNodeInputs(stack, sorted_groups)
rvc.setViewNode(stack)
log("stack inputs after setNodeInputs:", rvc.nodeConnections(stack, False))
log("viewNode:", rvc.viewNode())

# --- 4. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Show the session_manager panel, then screenshot it ---------------------
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
