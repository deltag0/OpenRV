"""Scenario: real `addButton` click opens "New Viewable" and creates a Stack
(COVERAGE §C1 -- the real UI trigger, closing the "outcome pinned via
rv.commands, not the menu click" gap left by `sm_create_views`).

`addThingSlot` dispatches by protocol string (session_manager.mu.in:2683);
"Stack" -> `addNodeOfType("RVStackGroup")` (line 2522), which wires the
CURRENT TREE SELECTION as inputs via `selectedConvertedSubComponents()` and
calls `setViewNode`. Deliberately avoids the movieproc-backed menu items
(Color Bars, Black, ...) which open a modal Create Image dialog
(`addMovieProc`, line 2564) -- out of scope headlessly, same as COVERAGE §C5.

Selects two media-free sources in the tree, clicks the real `addButton`,
clicks "Stack" in the real popup menu, and pins the resulting
`RVStackGroup` type/inputs/current-view outcome.
"""

import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import QtWidgets, open_tool_button_menu, click_menu_action, grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. Two media-free sources, both selected in the tree ---------------------
# Selected by node-NAME role, not a setUIName'd display string: any
# addSourceVerbose-created row's tree text is already built (with its
# default name) by the time this call returns -- loading pumps the event
# loop internally to wait for completion, so the deferred tree-rebuild timer
# has already fired before a later setUIName could affect it. Node identity
# is unaffected, and it's known immediately as the addSourceVerbose result.
srcA = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
groupA = rvc.nodeGroup(srcA)
srcB = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
groupB = rvc.nodeGroup(srcB)
log("groups:", groupA, groupB)

panel = sm.open_session_manager_panel(log=log)
tree_view = sm.find_view_tree(panel)
sm.select_row_by_node(tree_view, groupA)
sm.select_row_by_node(tree_view, groupB, extend=True)
selected = [i.data(sm.NODE_NAME_ROLE) for i in tree_view.selectionModel().selectedIndexes()]
log("tree selection before Add:", selected)

# --- 2. Click the real addButton -> "New Viewable" menu -> "Stack" ------------
# The default empty session already contains its own "defaultStack" scaffold
# node, so nodesOfType("RVStackGroup") isn't enough to identify OUR new one
# -- diff against a before-snapshot instead.
stacks_before = set(rvc.nodesOfType("RVStackGroup"))
add_button = panel.findChild(QtWidgets.QToolButton, "addButton")
menu = open_tool_button_menu(add_button)
click_menu_action(menu, "Stack")

new_stacks = set(rvc.nodesOfType("RVStackGroup")) - stacks_before
log("new RVStackGroup node(s) after real Add > Stack:", new_stacks)
if len(new_stacks) != 1:
    raise AssertionError(f"expected exactly one new RVStackGroup, got {new_stacks}")
stack = new_stacks.pop()
log("stack inputs:", rvc.nodeConnections(stack, False)[0])
log("current view:", rvc.viewNode())
if rvc.viewNode() != stack:
    log("NOTE: Mu leaves viewNode unchanged after Add > Stack (not defaultSequence/stack)")

# --- 3. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 4. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
