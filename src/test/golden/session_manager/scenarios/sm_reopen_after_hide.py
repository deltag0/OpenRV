"""Diagnostic: dock X-close then reopen via key."""
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

# Open
rvc.sendInternalEvent("key-down--x", "")
pump(800)
mode = sm.theMode()
log("after open: active", mode._active if mode else None)
win = qtutils.sessionWindow()
dock = win.findChild(QtWidgets.QDockWidget, "session_manager") if win else None
log("dock visible after open:", dock.isVisible() if dock else None)

# Simulate user closing dock titlebar X (hides widget, visibilityChanged fires)
if dock:
    dock.hide()
    pump(500)
log("after hide: active", mode._active if mode else None, "visible", dock.isVisible() if dock else None)

# Try reopen with x (3 attempts)
for i in range(3):
    rvc.sendInternalEvent("key-down--x", "")
    pump(800)
    log(f"reopen attempt {i+1}: active", mode._active, "visible", dock.isVisible() if dock else None)

diag.close()
