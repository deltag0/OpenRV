"""Scenario: session_manager clear session (COVERAGE §K2).

Builds a deterministic, media-free graph (two SMPTE-bars movieproc sources),
then clears the session with ``clearSession()`` -- the command that fires the
``after-clear-session`` event the session_manager binds at
``session_manager.mu:3179`` (``updateTreeEvent``). ``clearSession`` is exposed on
the Python command API (``rv_commands_setup.py:267``). Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

Behavioral end-state: the empty-default node set (no ``sourceGroup*`` nodes;
top nodes back to defaultLayout/defaultSequence/defaultStack).

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
log("source groups before clear:", rvc.nodesOfType("RVSourceGroup"))

# --- 2. Open the session_manager panel BEFORE clearing -------------------------
# This mirrors the real §K2 flow (panel already up when the session is cleared,
# so the after-clear-session handler rebuilds the tree to empty). Toggling the
# panel fresh AFTER a clearSession() segfaults RV headless, so open it first.
try:
    rvc.sendInternalEvent("key-down--x", "")
except Exception as e:
    log("sendInternalEvent key-down--x raised:", e)
pump(600)

# --- 3. Clear the session (the §K2 behavior) -----------------------------------
# clearSession() exists on the command API and fires after-clear-session.
rvc.clearSession()
pump(600)
log("source groups after clear:", rvc.nodesOfType("RVSourceGroup"))
log("nodes after clear:", rvc.nodes())

# --- 4. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Screenshot the (now-empty) panel ---------------------------------------
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
