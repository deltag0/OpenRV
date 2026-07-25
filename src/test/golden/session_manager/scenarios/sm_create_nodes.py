"""Scenario: session_manager Add -> Color / OCIO node creation (COVERAGE §C2).

Pins the BEHAVIORAL outcome of the "New Viewable" menu's Color and OCIO
entries. Those actions map to node types via addNodeOfType -> newNode(type, "")
(session_manager.mu :3405-3406, :2522-2537). The Dynamic node is intentionally
skipped: it is gated by RV_ENABLE_DYNAMIC_NODE (:3367) and is not created here.

From a fresh session:
  * create an RVColor node via newNode("RVColor", "")
  * create an OCIO node via newNode("OCIO", "")
  * leave the last-created node as the current view (mirrors addNodeOfType's
    setViewNode at :2534)

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

Modeled on tree_readonly.py (the template). Does NOT call os._exit.
"""

import os
import time

import rv.commands as rvc
import rv.qtutils as qtutils

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


try:
    from PySide6 import QtWidgets, QtCore
except ImportError:  # pragma: no cover - older Qt
    from PySide2 import QtWidgets, QtCore


def pump(ms):
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


# --- 1. Create RVColor and OCIO nodes (C2) -----------------------------------
color = rvc.newNode("RVColor", "")
log("created RVColor ->", color, "type=", rvc.nodeType(color))

ocio = rvc.newNode("OCIO", "")
log("created OCIO ->", ocio, "type=", rvc.nodeType(ocio))

# Mirror addNodeOfType: the created node becomes the current view.
rvc.setViewNode(ocio)
log("viewNode:", rvc.viewNode())
log("nodes:", rvc.nodes())

# --- 2. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 3. Show the session_manager panel, then screenshot it ---------------------
try:
    rvc.sendInternalEvent("key-down--x", "")
except Exception as e:
    log("sendInternalEvent key-down--x raised:", e)
pump(600)

win = qtutils.sessionWindow()
panel = win.findChild(QtWidgets.QWidget, "sessionManager") if win else None
log("sessionWindow:", bool(win), "panel(sessionManager) found:", bool(panel))

if panel is None:
    for dw in win.findChildren(QtWidgets.QDockWidget) if win else []:
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
