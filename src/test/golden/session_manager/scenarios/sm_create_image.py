"""Scenario: session_manager Create Image outcome (COVERAGE §C5).

The Create Image dialog (session_manager.mu:2564-2681) produces a media-free
movieproc source per chart/color type. It is modal (QDialog.show + accepted ->
makeImage -> addSourceVerbose), so we do NOT drive the dialog; we pin its
OUTCOME by calling addSourceVerbose with the movieproc specs the dialog builds,
for two DIFFERENT picture kinds:
  * "black"  -> group named "Black"       (dialog _cidName at :2653)
  * "solid"  -> group named "SolidColor"  (dialog _cidName at :2661)

The dialog also setUIName(nodeGroup(s), _cidName) at :2600, so we replicate that
naming to pin the full outcome.

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

Modeled on tree_readonly.py (the template). Does NOT call os._exit.
"""

import os
import time

import rv.commands as rvc
import rv.extra_commands as rve

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


# --- 1. Create the two Create-Image outcomes (different kinds) -----------------
# Media-free movieproc sources exactly as the dialog's makeImage() would build.
specs = [
    ("black,start=1,end=24,fps=24.movieproc", "Black"),
    ("solid,red=1,green=0,blue=0,start=1,end=24,fps=24.movieproc", "SolidColor"),
]
for spec, name in specs:
    s = rvc.addSourceVerbose([spec])
    grp = rvc.nodeGroup(s)
    rve.setUIName(grp, name)
    log("created", spec, "-> source", s, "group", grp, "uiName", rve.uiName(grp))

log("nodes:", rvc.nodes())
log("source groups:", rvc.nodesOfType("RVSourceGroup"))

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
