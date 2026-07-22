"""Scenario: session_manager delete-input OUTCOME (COVERAGE §E5).

The Inputs-tab "delete" button (inputsDeleteSlot, session_manager.mu:3022-3052)
removes the selected input(s) from the current view node via `setInputs`. Real
button/selection clicks can't be driven deterministically headless, so we pin the
*graph outcome*: an RVStackGroup that had three inputs ends up with the two that
survive a delete. This is the state the Python port's delete handler must produce.

Builds a deterministic, media-free graph of three SMPTE-bars movieproc sources,
wires all three into an RVStackGroup, then rewrites the stack's inputs to just two
(dropping the middle one) via setNodeInputs, and makes the stack the current view.

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


# --- 1. Build a deterministic, media-free graph --------------------------------
srcs = [
    "smptebars,start=1,end=24,fps=24.movieproc",
    "smptebars,start=1,end=24,fps=24.movieproc",
    "smptebars,start=1,end=24,fps=24.movieproc",
]
group_nodes = []
for s in srcs:
    src_node = rvc.addSourceVerbose([s])
    group_nodes.append(rvc.nodeGroup(src_node))
log("source group nodes:", group_nodes)

# --- 2. Create an RVStackGroup with all three sources as inputs ----------------
stack = rvc.newNode("RVStackGroup", "")
log("stack group node:", stack)
rvc.setNodeInputs(stack, group_nodes)
log("stack inputs (3):", rvc.nodeConnections(stack, False)[0])

# --- 3. Delete-input outcome: drop the middle input, keep the other two --------
remaining = [group_nodes[0], group_nodes[2]]
rvc.setNodeInputs(stack, remaining)
rvc.setViewNode(stack)

stack_inputs = rvc.nodeConnections(stack, False)[0]
log("stack inputs after delete (2):", stack_inputs)
log("viewNode:", rvc.viewNode())
assert len(stack_inputs) == 2, "expected exactly 2 inputs after delete, got %r" % (stack_inputs,)

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
