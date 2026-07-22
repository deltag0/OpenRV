"""Scenario: session_manager sub-component image request OUTCOME (COVERAGE §D3, §J8).

Clicking a source's status column in the tree views a sub-component
(view/layer/channel) by writing `<sourceNode>.request.imageComponent` and reloading
(setImageRequest / setNodeRequest, session_manager.mu:519-606, 2400-2412). The
property value is a typed string vector, e.g. a View sub-component is
`["view", <viewName>]` (subComponentPropValue, :567-569).

Real status-column clicks aren't deterministic headless, so we pin the *graph
outcome*: after "viewing" a View sub-component, the source node carries
`request.imageComponent = ["view", "left"]`. This is exactly what setNodeRequest does
(setStringProperty(node + ".request.imageComponent", value, true)).

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

# setNodeRequest writes on the source node (sourceNodeOfGroup), the RVFileSource.
file_source = find_node_of_type(source_group, "RVFileSource")
log("internal RVFileSource node:", file_source)
assert file_source is not None, "no RVFileSource inside RVSourceGroup"

# --- 2. Write the sub-component image request (View sub-component form) ---------
# subComponentPropValue for a ViewSubComponent -> ["view", <viewName>].
request_prop = file_source + ".request.imageComponent"
value = ["view", "left"]

if not rvc.propertyExists(request_prop):
    rvc.newProperty(request_prop, rvc.StringType, 1)

# Mirror setNodeRequest: setStringProperty(node + ".request.imageComponent", value, true)
rvc.setStringProperty(request_prop, value, True)

log("request.imageComponent =", rvc.getStringProperty(request_prop))

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
