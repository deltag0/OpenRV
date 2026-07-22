"""Scenario: session_manager LayoutGroup edit mode (F3).

Pins the BEHAVIORAL outcome of the Layout editor: create an RVLayoutGroup over
two sources, then write the properties LayoutGroup_edit_mode writes on the
group's RVLayoutGroup node:
  * #RVLayoutGroup.layout.mode        (string) -> "grid"
  * #RVLayoutGroup.layout.spacing     (float)  -> 0.75
  * #RVLayoutGroup.layout.gridRows    (int)    -> 2
  * #RVLayoutGroup.layout.gridColumns (int)    -> 3

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
srcs = [
    "smptebars,start=1,end=24,fps=24.movieproc",
    "smptebars,start=1,end=24,fps=24.movieproc",
]
for s in srcs:
    rvc.addSourceVerbose([s])

source_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", source_groups)

# --- 2. Create RVLayoutGroup over the two sources ------------------------------
layout_group = rvc.newNode("RVLayoutGroup", "")
log("layout_group:", layout_group)
rvc.setNodeInputs(layout_group, source_groups)
log("layout_group inputs:", rvc.nodeConnections(layout_group, False)[0])

layout_node = find_node_of_type(layout_group, "RVLayoutGroup")
log("RVLayoutGroup node:", layout_node)
assert layout_node is not None, "no RVLayoutGroup node found"

# --- 3. Write the Layout editor properties -------------------------------------
mode_prop = layout_node + ".layout.mode"
spacing_prop = layout_node + ".layout.spacing"
rows_prop = layout_node + ".layout.gridRows"
cols_prop = layout_node + ".layout.gridColumns"

if not rvc.propertyExists(mode_prop):
    rvc.newProperty(mode_prop, rvc.StringType, 1)
if not rvc.propertyExists(spacing_prop):
    rvc.newProperty(spacing_prop, rvc.FloatType, 1)
if not rvc.propertyExists(rows_prop):
    rvc.newProperty(rows_prop, rvc.IntType, 1)
if not rvc.propertyExists(cols_prop):
    rvc.newProperty(cols_prop, rvc.IntType, 1)

rvc.setStringProperty(mode_prop, ["grid"], True)
rvc.setFloatProperty(spacing_prop, [0.75], True)
rvc.setIntProperty(rows_prop, [2], True)
rvc.setIntProperty(cols_prop, [3], True)

log("layout.mode =", rvc.getStringProperty(mode_prop))
log("layout.spacing =", rvc.getFloatProperty(spacing_prop))
log("layout.gridRows =", rvc.getIntProperty(rows_prop))
log("layout.gridColumns =", rvc.getIntProperty(cols_prop))

# --- 4. Make the layout the current view ---------------------------------------
rvc.setViewNode(layout_group)
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
