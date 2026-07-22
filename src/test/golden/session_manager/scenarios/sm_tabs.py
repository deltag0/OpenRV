"""Scenario: per-node tab selection persisted (COVERAGE §F13 / §J5).

The session_manager stores the currently-selected Edit/Inputs tab per view node in
`<viewNode>.sm_state.tab` (int). `saveTabState` does `set("%s.sm_state.tab" % viewNode(),
_tabWidget.currentIndex())` (session_manager.mu:3054-3057), where `set` creates the
IntType property if absent then `setIntProperty(..., true)`.

Here we build an RVStackGroup over two media-free sources, write its per-node tab state
via newProperty + setIntProperty exactly as the Mu `set` helper does, then make it the
current view. We pin:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png
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


# --- 1. Build a deterministic, media-free graph: RVStackGroup over 2 sources ---
srcs = []
for _ in range(2):
    s = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
    srcs.append(rvc.nodeGroup(s))
log("source groups:", srcs)

stack = rvc.newNode("RVStackGroup", "")
rve.setUIName(stack, "MyStack")
rvc.setNodeInputs(stack, srcs)
log("stack:", stack, "inputs:", rvc.nodeConnections(stack, False)[0])

# --- 2. Write the per-node tab state exactly as saveTabState does --------------
# set(prop, currentIndex()) -> cprop(IntType) then setIntProperty(prop, [v], true).
tab_prop = "%s.sm_state.tab" % stack
if not rvc.propertyExists(tab_prop):
    rvc.newProperty(tab_prop, rvc.IntType, 1)
rvc.setIntProperty(tab_prop, [1], True)  # 1 == Edit tab
log("sm_state.tab =", rvc.getIntProperty(tab_prop))

# --- 3. Make the stack the current view ----------------------------------------
rvc.setViewNode(stack)
log("viewNode:", rvc.viewNode())

# --- 4. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Show the panel and screenshot it ---------------------------------------
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
