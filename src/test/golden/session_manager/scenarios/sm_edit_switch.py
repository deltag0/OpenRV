"""Scenario: session_manager Switch edit mode (F9) behavioral baseline.

Pins the BEHAVIORAL outcome of the Switch edit mode: create an RVSwitchGroup
over two media-free sources, then set the editor-controlled properties on the
group's internal RVSwitch node exactly as Switch_edit_mode.mu writes them:
    mode.alignStartFrames (Int)    -- Switch_edit_mode.mu:187,211
    mode.useCutInfo       (Int)    -- :191,218
    output.input          (String) -- :141 (selected input name)
    output.size           (Int,2)  -- :151,160

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

Modeled on tree_readonly.py (the template). Does NOT call os._exit.
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


def ensure_prop(name, ptype, width):
    if not rvc.propertyExists(name):
        rvc.newProperty(name, ptype, width)
        log("  created property", name)


def set_int(node, path, values):
    name = node + "." + path
    ensure_prop(name, rvc.IntType, len(values))
    rvc.setIntProperty(name, values, True)
    got = list(rvc.getIntProperty(name))
    log("  set", name, "=", values, "-> readback", got)
    assert got == list(values), "int readback mismatch for %s" % name


def set_string(node, path, value):
    name = node + "." + path
    ensure_prop(name, rvc.StringType, 1)
    rvc.setStringProperty(name, [value], True)
    got = list(rvc.getStringProperty(name))
    log("  set", name, "=", value, "-> readback", got)
    assert got == [value], "string readback mismatch for %s" % name


# --- 1. Build a deterministic, media-free graph --------------------------------
srcs = [
    "smptebars,start=1,end=24,fps=24.movieproc",
    "smptebars,start=1,end=24,fps=24.movieproc",
]
for s in srcs:
    rvc.addSourceVerbose([s])

source_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", source_groups)

# --- 2. Create the RVSwitchGroup over the two sources --------------------------
grp = rvc.newNode("RVSwitchGroup", "")
rvc.setNodeInputs(grp, source_groups)
rvc.setViewNode(grp)
log("created group:", grp, "type", rvc.nodeType(grp))

# --- 3. Find the internal RVSwitch node ----------------------------------------
sw = None
for n in rvc.nodesInGroup(grp):
    if rvc.nodeType(n) == "RVSwitch":
        sw = n
        break
log("internal RVSwitch node:", sw)
assert sw is not None, "no RVSwitch node found in group"

# The editor picks the selected input by node name from the group's inputs.
selected_input = source_groups[0]

# --- 4. Set the editor-controlled properties (F9) ------------------------------
set_int(sw, "mode.alignStartFrames", [1])
set_int(sw, "mode.useCutInfo", [1])
set_string(sw, "output.input", selected_input)
set_int(sw, "output.size", [720, 480])

# --- 5. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 6. Show the session_manager panel, then screenshot it ---------------------
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
