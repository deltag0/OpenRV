"""Diagnostic: session_manager toggle path and panel visibility."""
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
except ImportError:
    from PySide2 import QtWidgets, QtCore


def pump(ms):
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
pump(400)

import session_manager as sm

log("session_manager module:", sm.__file__)
log("theMode before toggle:", sm.theMode())
log("sessionManagerReady:", sm.sessionManagerReady())

try:
    log("category enabled:", rvc.isEventCategoryEnabled("sessionmanager_category"))
except Exception as e:
    log("category check failed:", e)

for attempt in ("key-down--x", "mode-manager-toggle-mode"):
    try:
        if attempt == "key-down--x":
            rvc.sendInternalEvent("key-down--x", "")
        else:
            rvc.sendInternalEvent("mode-manager-toggle-mode", "session_manager")
    except Exception as e:
        log(attempt, "raised:", e)
    pump(800)

    mode = sm.theMode()
    log(f"after {attempt}:")
    log("  theMode:", mode)
    log("  mode._active:", getattr(mode, "_active", "?") if mode else None)

    win = qtutils.sessionWindow()
    log("  sessionWindow:", bool(win))
    dock = None
    if win:
        dock = win.findChild(QtWidgets.QDockWidget, "session_manager")
        if dock is None:
            for dw in win.findChildren(QtWidgets.QDockWidget):
                log("  dock candidate:", dw.objectName(), "vis", dw.isVisible())
                if "session" in dw.objectName().lower():
                    dock = dw
    if dock:
        log("  dock:", dock.objectName(), "visible", dock.isVisible(), "geom", dock.width(), dock.height())
    else:
        log("  dock: NOT FOUND")

    try:
        active = rvc.activateMode("session_manager")
        log("  activateMode return:", active, "active?", getattr(active, "_active", "?") if active else None)
    except Exception as e:
        log("  activateMode error:", e)

diag.close()
