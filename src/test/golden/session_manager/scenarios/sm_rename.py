"""Scenario: session_manager inline rename (COVERAGE §I7).

Builds a deterministic, media-free graph (one SMPTE-bars movieproc source),
renames its source GROUP via ``setUIName`` -- mirroring the inline-rename slot
(``session_manager.mu:1455`` ``setUIName(node, item.text())``) -- then makes it
the current view via ``setViewNode``. Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

The behavioral end-state is the renamed source group whose ``ui.name`` is
"MyRenamedView" and which is the session view node.

Harness notes (see tree_readonly.py): -pyeval runs before the Qt loop, so we
pump events before grab(); output must go to files, not stdout.
"""

import os
import time

import rv.commands as rvc
import rv.extra_commands as rve  # setUIName / uiName live here, not in rv.commands

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- Qt bindings (Qt6 build -> PySide6; fall back to PySide2) ------------------
try:
    from PySide6 import QtWidgets, QtCore
    import shiboken6 as shiboken
except ImportError:  # pragma: no cover - older Qt
    from PySide2 import QtWidgets, QtCore
    import shiboken2 as shiboken

import rv.qtutils as qtutils


def pump(ms):
    """Pump the Qt event loop for ~ms without a bare sleep."""
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


# --- 1. Build a deterministic, media-free graph --------------------------------
src = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
grp = rvc.nodeGroup(src)
log("added source node:", src, "group:", grp)

# --- 2. Rename the source group (the §I7 behavior) + make it current view ------
rve.setUIName(grp, "MyRenamedView")
rvc.setViewNode(grp)
log("ui name after rename:", rve.uiName(grp))
log("viewNode:", rvc.viewNode())
log("nodes:", rvc.nodes())

# --- 3. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 4. Show the session_manager panel, then screenshot it ---------------------
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
