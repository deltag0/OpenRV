"""Scenario: folder child sort order (COVERAGE §G5 / §J5).

When a folder's children are (re)ordered, the mode's `assignSortOrder` walks the folder's
child rows and calls `setSortKeyInParent(childNode, folderNode, index)` for index 0,1,2...
(session_manager.mu:482-506). `setSortKeyInParent` (:293-332) writes two per-child
properties:
  * `<child>.sm_state.sortKeyParent` (StringType) -> [folderNode]
  * `<child>.sm_state.sortKey`       (IntType)    -> [index]
Together `(sortKeyParent[i], sortKey[i])` maps "when displayed under folder <parent>, this
child's sort key is <int>". `sortKeyInParent` (:268-291) reads them back by indexOf(parent).

Here we build an RVFolderGroup over 3 sources whose UI names (Cam_C, Cam_A, Cam_B) differ
from their creation/input order, then assign an EXPLICIT alphabetical sort order
(Cam_A=0, Cam_B=1, Cam_C=2) by writing sortKey/sortKeyParent on each child exactly as
`setSortKeyInParent` does for the first-time (property-absent) branch. This is
deterministic and meaningful: the pinned keys reorder the children away from input order.

We pin:
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


def set_sort_key_in_parent(node, parent, value):
    """Mirror session_manager.mu setSortKeyInParent (first-time / absent branch).

    set(sortKeyParent, parent) -> StringType [parent]; set(sortKey, value) -> IntType [value].
    """
    p_parent = "%s.sm_state.sortKeyParent" % node
    p_key = "%s.sm_state.sortKey" % node
    if not rvc.propertyExists(p_parent):
        rvc.newProperty(p_parent, rvc.StringType, 1)
    if not rvc.propertyExists(p_key):
        rvc.newProperty(p_key, rvc.IntType, 1)
    rvc.setStringProperty(p_parent, [parent], True)
    rvc.setIntProperty(p_key, [value], True)


# --- 1. Build a folder over 3 named sources ------------------------------------
# Creation/input order is Cam_C, Cam_A, Cam_B (deliberately unsorted).
names = ["Cam_C", "Cam_A", "Cam_B"]
children = []
for nm in names:
    s = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
    g = rvc.nodeGroup(s)
    rve.setUIName(g, nm)
    children.append(g)

folder = rvc.newNode("RVFolderGroup", "")
rve.setUIName(folder, "MyFolder")
rvc.setNodeInputs(folder, children)
log("folder:", folder, "children (input order):", rvc.nodeConnections(folder, False)[0])

# --- 2. Assign an explicit alphabetical sort order (assignSortOrder outcome) ----
# Cam_A -> 0, Cam_B -> 1, Cam_C -> 2.  children[] is [Cam_C, Cam_A, Cam_B].
sort_index = {"Cam_A": 0, "Cam_B": 1, "Cam_C": 2}
for nm, child in zip(names, children):
    set_sort_key_in_parent(child, folder, sort_index[nm])
    log(
        nm, child,
        "sortKeyParent =", rvc.getStringProperty("%s.sm_state.sortKeyParent" % child),
        "sortKey =", rvc.getIntProperty("%s.sm_state.sortKey" % child),
    )

# --- 3. Make the folder the current view ---------------------------------------
rvc.setViewNode(folder)
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
