"""Scenario: session_manager delete view node (COVERAGE §I8).

Builds a deterministic, media-free graph (two SMPTE-bars movieproc sources),
creates an ``RVStackGroup`` over both source groups (as the "Create View" path
does: ``newNode`` + set inputs + ``setViewNode``), then deletes that stack via
``deleteNode`` -- mirroring the ``deleteViewableSlot`` single-parent branch
(``session_manager.mu:2755`` -> ``deleteNode(node)``). Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

Behavioral end-state: the stack group is GONE, the two source groups remain
(i.e. the graph is back to a plain two-source session).

Harness notes (see tree_readonly.py): -pyeval runs before the Qt loop, so we
pump events before grab(); output must go to files, not stdout.
"""

import os
import time

import rv.commands as rvc

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


# --- 1. Build a deterministic, media-free graph (2 sources) --------------------
for _ in range(2):
    rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
src_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", src_groups)

# --- 2. Create an RVStackGroup over both sources, make it current --------------
stack = rvc.newNode("RVStackGroup", "")
rvc.setNodeInputs(stack, src_groups)
rvc.setViewNode(stack)
log("created stack:", stack, "inputs:", rvc.nodeConnections(stack, False)[0])
log("nodes with stack:", rvc.nodesOfType("RVStackGroup"))

# --- 3. Delete the stack view node (the §I8 behavior) --------------------------
rvc.deleteNode(stack)
log("stack exists after delete:", rvc.nodeExists(stack))
log("source groups after delete:", rvc.nodesOfType("RVSourceGroup"))
log("stack groups after delete:", rvc.nodesOfType("RVStackGroup"))

# --- 4. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Show the session_manager panel, then screenshot it ---------------------
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
