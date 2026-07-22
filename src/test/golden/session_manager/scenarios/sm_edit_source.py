"""Scenario: session_manager SourceGroup edit mode (F6).

Pins the BEHAVIORAL outcome of the Source cut editor: add one source, then write
the properties SourceGroup_edit_mode writes on the source's RVFileSource node:
  * #RVFileSource.cut.in  (int) -> 5
  * #RVFileSource.cut.out (int) -> 20

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


# --- 1. Add a single deterministic, media-free source --------------------------
rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])

source_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", source_groups)
source_group = source_groups[0]

file_source = find_node_of_type(source_group, "RVFileSource")
log("internal RVFileSource node:", file_source)
assert file_source is not None, "no RVFileSource inside RVSourceGroup"

# --- 2. Write the Source cut editor properties ---------------------------------
cutin_prop = file_source + ".cut.in"
cutout_prop = file_source + ".cut.out"

if not rvc.propertyExists(cutin_prop):
    rvc.newProperty(cutin_prop, rvc.IntType, 1)
if not rvc.propertyExists(cutout_prop):
    rvc.newProperty(cutout_prop, rvc.IntType, 1)

rvc.setIntProperty(cutin_prop, [5], True)
rvc.setIntProperty(cutout_prop, [20], True)

log("cut.in =", rvc.getIntProperty(cutin_prop))
log("cut.out =", rvc.getIntProperty(cutout_prop))

# --- 3. Make the source the current view ---------------------------------------
rvc.setViewNode(source_group)
log("viewNode:", rvc.viewNode())

# --- 4. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Show the panel and screenshot it ---------------------------------------
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
