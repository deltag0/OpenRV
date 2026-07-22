"""Scenario: reparent (MOVE) outcome — the graph result of dragging a node from
one folder to another with the default MoveAction (COVERAGE §G1).

Real drag gestures can't be driven headlessly (synthesized QDropEvents have a null
source(), see §G), so we pin the *outcome* via the equivalent `rv.commands`: the node
leaves FolderA and joins FolderB. This is the graph state the Python port's drop handler
must produce.
"""

import os
import time

import rv.commands as rvc
import rv.extra_commands as rve

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")
def log(*a): print(*a, file=diag, flush=True)

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore
import rv.qtutils as qtutils

def pump(ms):
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)

# FolderA[source], FolderB[]
s = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
src = rvc.nodeGroup(s)
fa = rvc.newNode("RVFolderGroup", ""); rve.setUIName(fa, "FolderA"); rvc.setNodeInputs(fa, [src])
fb = rvc.newNode("RVFolderGroup", ""); rve.setUIName(fb, "FolderB")

# MOVE: remove from FolderA, add to FolderB (MoveAction outcome).
rvc.setNodeInputs(fa, [])
rvc.setNodeInputs(fb, [src])
rvc.setViewNode(fb)
log("fa inputs", rvc.nodeConnections(fa, False)[0], "| fb inputs", rvc.nodeConnections(fb, False)[0])

rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)

rvc.sendInternalEvent("key-down--x", ""); pump(600)
win = qtutils.sessionWindow()
panel = win.findChild(QtWidgets.QWidget, "sessionManager") if win else None
if panel is not None:
    if not panel.isVisible():
        panel.show()
    pump(400)
    panel.grab().save(os.path.join(out_dir, "panel.png"), "PNG")
    log("panel grabbed")
else:
    log("PANEL NOT FOUND")
diag.close()
