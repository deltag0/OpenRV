"""Scenario: session_manager Composite edit mode (F1).

Pins the BEHAVIORAL outcome of the Composite editor: create an RVStackGroup over
two sources, then write the properties the Composite_edit_mode writes on the
group's internal RVStack node:
  * #RVStack.composite.type          (string)  -> "dissolve"
  * #RVStack.composite.dissolveAmount(float)   -> 0.35

Then open the session_manager panel with the stack as the current view (so the
Composite editor UI renders) and capture:
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
log("nodes after add:", rvc.nodes())

source_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", source_groups)

# --- 2. Create RVStackGroup over the two sources -------------------------------
stack_group = rvc.newNode("RVStackGroup", "")
log("stack_group:", stack_group)
rvc.setNodeInputs(stack_group, source_groups)
log("stack_group inputs:", rvc.nodeConnections(stack_group, False)[0])

# Find the internal RVStack node.
stack_node = None
for n in rvc.nodesInGroup(stack_group):
    if rvc.nodeType(n) == "RVStack":
        stack_node = n
        break
log("internal RVStack node:", stack_node)
assert stack_node is not None, "no RVStack inside RVStackGroup"

# --- 3. Write the Composite editor properties ----------------------------------
type_prop = stack_node + ".composite.type"
diss_prop = stack_node + ".composite.dissolveAmount"

if not rvc.propertyExists(type_prop):
    rvc.newProperty(type_prop, rvc.StringType, 1)
if not rvc.propertyExists(diss_prop):
    rvc.newProperty(diss_prop, rvc.FloatType, 1)

rvc.setStringProperty(type_prop, ["dissolve"], True)
rvc.setFloatProperty(diss_prop, [0.35], True)

log("composite.type =", rvc.getStringProperty(type_prop))
log("composite.dissolveAmount =", rvc.getFloatProperty(diss_prop))

# --- 4. Make the stack the current view ----------------------------------------
rvc.setViewNode(stack_group)
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
