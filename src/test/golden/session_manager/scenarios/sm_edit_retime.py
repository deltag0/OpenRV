"""Scenario: session_manager RetimeGroup edit mode (F4).

Pins the BEHAVIORAL outcome of the Retime editor: create an RVRetimeGroup over
one source, then write the properties RetimeGroup_edit_mode writes on the
group's internal RVRetime node:
  * #RVRetime.visual.scale  (float) -> 0.5
  * #RVRetime.visual.offset (float) -> 2.0
  * #RVRetime.output.fps    (float) -> 30.0

Captures:
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


def find_node_of_type(group, typename):
    for cand in [group] + list(rvc.nodesInGroup(group)):
        if rvc.nodeType(cand) == typename:
            return cand
    return None


# --- 1. Build a deterministic, media-free graph --------------------------------
rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])

source_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", source_groups)

# --- 2. Create RVRetimeGroup over the single source ----------------------------
retime_group = rvc.newNode("RVRetimeGroup", "")
log("retime_group:", retime_group)
rvc.setNodeInputs(retime_group, source_groups)
log("retime_group inputs:", rvc.nodeConnections(retime_group, False)[0])

retime_node = find_node_of_type(retime_group, "RVRetime")
log("internal RVRetime node:", retime_node)
assert retime_node is not None, "no RVRetime inside RVRetimeGroup"

# --- 3. Write the Retime editor properties -------------------------------------
vscale_prop = retime_node + ".visual.scale"
voffset_prop = retime_node + ".visual.offset"
fps_prop = retime_node + ".output.fps"

if not rvc.propertyExists(vscale_prop):
    rvc.newProperty(vscale_prop, rvc.FloatType, 1)
if not rvc.propertyExists(voffset_prop):
    rvc.newProperty(voffset_prop, rvc.FloatType, 1)
if not rvc.propertyExists(fps_prop):
    rvc.newProperty(fps_prop, rvc.FloatType, 1)

rvc.setFloatProperty(vscale_prop, [0.5], True)
rvc.setFloatProperty(voffset_prop, [2.0], True)
rvc.setFloatProperty(fps_prop, [30.0], True)

log("visual.scale =", rvc.getFloatProperty(vscale_prop))
log("visual.offset =", rvc.getFloatProperty(voffset_prop))
log("output.fps =", rvc.getFloatProperty(fps_prop))

# --- 4. Make the retime the current view ---------------------------------------
rvc.setViewNode(retime_group)
log("viewNode:", rvc.viewNode())

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
