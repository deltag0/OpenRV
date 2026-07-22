"""Scenario: session_manager FolderGroup edit mode (F2) behavioral baseline.

Pins the BEHAVIORAL outcome of the Folder View editor: create an RVFolderGroup
then set the single property the FolderGroup_edit_mode writes on the group node,
exactly as FolderGroup_edit_mode.mu:52 does via set("#RVFolderGroup.mode.viewType"):
    mode.viewType (String) -> "layout"

The editor's combo offers "switch" / "layout" / "stack" (:109-111); we set
"layout" (the default view type for a folder). The property lives on the
RVFolderGroup group node itself.

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png

Modeled on tree_readonly.py (the template). Does NOT call os._exit.
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


def ensure_prop(name, ptype, width):
    if not rvc.propertyExists(name):
        rvc.newProperty(name, ptype, width)
        log("  created property", name)


def set_string(node, path, value):
    name = node + "." + path
    ensure_prop(name, rvc.StringType, 1)
    rvc.setStringProperty(name, [value], True)
    got = list(rvc.getStringProperty(name))
    log("  set", name, "=", value, "-> readback", got)
    assert got == [value], "string readback mismatch for %s" % name


# --- 1. Build a deterministic, media-free graph --------------------------------
srcs = [
    "smptebars,start=1,end=24,fps=24.movieproc",
    "smptebars,start=1,end=24,fps=24.movieproc",
]
for s in srcs:
    rvc.addSourceVerbose([s])

source_groups = rvc.nodesOfType("RVSourceGroup")
log("source groups:", source_groups)

# --- 2. Create the RVFolderGroup over the two sources --------------------------
grp = rvc.newNode("RVFolderGroup", "")
rvc.setNodeInputs(grp, source_groups)
rvc.setViewNode(grp)
log("created group:", grp, "type", rvc.nodeType(grp))

# --- 3. Set the editor-controlled property (F2) --------------------------------
# FolderGroup_edit_mode writes mode.viewType on the RVFolderGroup group node.
set_string(grp, "mode.viewType", "layout")

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
