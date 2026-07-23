"""Scenario: real `folderButton` click -> "From Selection" wraps two
real-media nodes in a new folder (COVERAGE §C8 -- the real UI trigger,
complementing `sm_folders.py`'s direct `newNode`/`setNodeInputs` pin of the
same outcome).

`newFolderSlot(which=2)` (session_manager.mu.in:2699, wired at line 3534)
is "From Selection": builds a new `RVFolderGroup` over the selected tree
nodes and makes it the current view. Selects two real-media (top-level, no
prior folder parent) sources in the tree, clicks the real `folderButton`,
clicks "From Selection" in the real popup menu, and pins the resulting
folder/inputs/current-view outcome.

OPEN ISSUE: `open_tool_button_menu(folder_button)` was observed to hang
indefinitely during macOS smoke-testing -- see the note on
`qt_scenario_utils.open_tool_button_menu` for what's known/unproven about
it. Verify on the pinned Linux + Xvfb target before trusting this scenario;
if it also hangs there, drop/rework it and note COVERAGE §C8's real-trigger
row as attempted-but-unreliable (outcome stays pinned by `sm_folders.py`),
per VERIFICATION.md's DoD rule 3.
"""

import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import QtWidgets, open_tool_button_menu, click_menu_action, grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. Two real-media sources, quiesced, both selected in the tree ------------
# Selected by node-NAME role, not display text -- see sm_button_select_current.py
# for why display text can't be trusted for real-media source rows here.
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE], log=log
)
sm.quiesce_real_previews(source_nodes, log=log)

panel = sm.open_session_manager_panel(log=log)
tree_view = sm.find_view_tree(panel)
sm.select_row_by_node(tree_view, group_nodes[0])
sm.select_row_by_node(tree_view, group_nodes[1], extend=True)
log("tree selection before folder-from-selection:",
    [i.data(sm.NODE_NAME_ROLE) for i in tree_view.selectionModel().selectedIndexes()])

# --- 2. Click the real folderButton -> "New Folder" menu -> "From Selection" -
folder_button = panel.findChild(QtWidgets.QToolButton, "folderButton")
menu = open_tool_button_menu(folder_button)
click_menu_action(menu, "From Selection")

new_folders = rvc.nodesOfType("RVFolderGroup")
log("RVFolderGroup nodes after real Folder > From Selection:", new_folders)
if not new_folders:
    raise AssertionError("folderButton > From Selection did not create an RVFolderGroup")
folder = new_folders[0]
log("folder inputs:", rvc.nodeConnections(folder, False)[0])
log("current view:", rvc.viewNode())
if rvc.viewNode() != folder:
    log("NOTE: Mu leaves viewNode unchanged after Folder > From Selection")
if set(rvc.nodeConnections(folder, False)[0]) != set(group_nodes):
    raise AssertionError("new folder does not contain exactly the selected nodes")

# --- 3. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 4. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
