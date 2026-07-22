"""Scenario: session_manager Stack edit mode (F7) behavioral baseline.

Pins the BEHAVIORAL outcome of the Stack edit mode: create an RVStackGroup over
two media-free sources, then set the editor-controlled properties on the group's
internal RVStack node exactly as Stack_edit_mode.mu writes them:
    mode.alignStartFrames (Int)   -- Stack_edit_mode.mu:253,290
    mode.useCutInfo       (Int)   -- :261,304
    output.fps            (Float) -- :197
    output.size           (Int,2) -- :213,222

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


def set_float(node, path, value):
    name = node + "." + path
    ensure_prop(name, rvc.FloatType, 1)
    rvc.setFloatProperty(name, [value], True)
    got = list(rvc.getFloatProperty(name))
    log("  set", name, "=", value, "-> readback", got)
    assert abs(got[0] - value) < 1e-6, "float readback mismatch for %s" % name


# --- 1. Build a deterministic, media-free graph --------------------------------
srcs = [
    "smptebars,start=1,end=24,fps=24.movieproc",
    "smptebars,start=1,end=24,fps=24.movieproc",
]
for s in srcs:
    rvc.addSourceVerbose([s])

source_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", source_groups)

# --- 2. Create the RVStackGroup over the two sources ---------------------------
grp = rvc.newNode("RVStackGroup", "")
rvc.setNodeInputs(grp, source_groups)
rvc.setViewNode(grp)
log("created group:", grp, "type", rvc.nodeType(grp))

# --- 3. Find the internal RVStack node -----------------------------------------
stk = None
for n in rvc.nodesInGroup(grp):
    if rvc.nodeType(n) == "RVStack":
        stk = n
        break
log("internal RVStack node:", stk)
assert stk is not None, "no RVStack node found in group"

# --- 4. Set the editor-controlled properties (F7) ------------------------------
set_int(stk, "mode.alignStartFrames", [1])
set_int(stk, "mode.useCutInfo", [1])
set_float(stk, "output.fps", 30.0)
set_int(stk, "output.size", [1920, 1080])

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
