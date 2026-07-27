"""Scenario: transform_manip edit mode OUTCOME (COVERAGE §F11).

transform_manip is POINTER-driven (pointer--move/drag on the view). Per the project
rule we do NOT synthesize pointer input; we pin the equivalent *graph outcome* using
the same property writes the manipulator performs (transform_manip.mu:240-362):
  * <tform>.transform.translate ([x,y] float)
  * <tform>.transform.scale     ([sx,sy] float)
on one of the RVTransform2D nodes inside an RVLayoutGroup.

An RVLayoutGroup in "manual" layout over 2 sources contains one internal
RVTransform2D per input (the nodes transform_manip discovers via
metaEvaluateClosestByType("RVTransform2D")). We locate them deterministically via
nodesInGroup + nodeType "RVTransform2D", pick the first (sorted by name), and write
its transform. This is the state the Python port's manipulator drag must produce.

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png
"""

import os
import time

import rv.commands as rvc

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


# --- 1. Build a deterministic, media-free graph --------------------------------
srcs = [
    "smptebars,start=1,end=24,fps=24.movieproc",
    "smptebars,start=1,end=24,fps=24.movieproc",
]
for s in srcs:
    rvc.addSourceVerbose([s])

source_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", source_groups)

# --- 2. Create RVLayoutGroup over the two sources, in manual layout ------------
layout_group = rvc.newNode("RVLayoutGroup", "")
log("layout_group:", layout_group)
rvc.setNodeInputs(layout_group, source_groups)
log("layout_group inputs:", rvc.nodeConnections(layout_group, False)[0])

layout_node = None
for cand in [layout_group] + list(rvc.nodesInGroup(layout_group)):
    if rvc.nodeType(cand) == "RVLayoutGroup":
        layout_node = cand
        break
log("RVLayoutGroup node:", layout_node)
assert layout_node is not None, "no RVLayoutGroup node found"

# Manual layout is the mode the transform manipulator operates in.
mode_prop = layout_node + ".layout.mode"
if not rvc.propertyExists(mode_prop):
    rvc.newProperty(mode_prop, rvc.StringType, 1)
rvc.setStringProperty(mode_prop, ["manual"], True)
log("layout.mode =", rvc.getStringProperty(mode_prop))

rvc.setViewNode(layout_group)
pump(200)  # let the layout build its per-input RVTransform2D nodes

# --- 3. Locate the internal RVTransform2D nodes deterministically --------------
tform_nodes = sorted(
    n for n in rvc.nodesInGroup(layout_group) if rvc.nodeType(n) == "RVTransform2D"
)
log("RVTransform2D nodes:", tform_nodes)
assert tform_nodes, "no RVTransform2D nodes found inside RVLayoutGroup"

tform = tform_nodes[0]
log("editing transform node:", tform)

# --- 4. Write the transform_manip properties (translate + scale) ---------------
trans_prop = tform + ".transform.translate"
scale_prop = tform + ".transform.scale"

if not rvc.propertyExists(trans_prop):
    rvc.newProperty(trans_prop, rvc.FloatType, 2)
if not rvc.propertyExists(scale_prop):
    rvc.newProperty(scale_prop, rvc.FloatType, 2)

rvc.setFloatProperty(trans_prop, [0.25, -0.1], True)
rvc.setFloatProperty(scale_prop, [1.5, 1.5], True)

log("transform.translate =", rvc.getFloatProperty(trans_prop))
log("transform.scale =", rvc.getFloatProperty(scale_prop))

# Sync transform_manip tag properties (behavioral parity with Mu).
try:
    rvc.activateMode("transform_manip")
    from transform_manip import sync_editing_tags

    sync_editing_tags()
except Exception as exc:
    log("sync tmanip tags:", exc)
pump(100)

# --- 5. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 6. Show the panel and screenshot it ---------------------------------------
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
