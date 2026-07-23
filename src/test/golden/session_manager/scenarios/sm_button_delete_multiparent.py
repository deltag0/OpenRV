"""Scenario: real `deleteButton` click on a multi-parent node pins
`removeInput`, not `deleteNode` (COVERAGE §I8 multi-parent branch -- no
existing scenario covers this half of `deleteViewableSlot`).

`deleteViewableSlot` (session_manager.mu.in:2755-2792): if the selected
item's parent is an `RVFolderGroup` AND the node has more than one
`RVFolderGroup` output, it calls `removeInput(parent, node)` (detach from
just that folder); otherwise `deleteNode(node)`. Builds one real-media
source shared by two folders, selects its row under the FIRST folder
specifically (`_sm_common.find_child_index_by_text`, since the same node
appears once per parent and the specific occurrence determines which
branch fires), clicks the real `deleteButton`, and asserts the node
survives (still an input of the second folder) while being gone from the
first.
"""

import os

import rv.commands as rvc
import rv.extra_commands as rve

import _sm_common as sm
from qt_scenario_utils import QtWidgets, click_button, grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. One real-media source, shared by two folders ---------------------------
# The source's row is found by node-NAME role, not setUIName/display text --
# see sm_button_select_current.py for why a post-hoc rename on an
# already-loaded real source never reaches the tree's rendered row text.
# Folder names ARE named right after creation (before any pump), so those
# renames land before the tree's first (lazy) build and work as expected.
source_nodes, group_nodes = sm.add_real_sources([sm.IMAGE_FIXTURE], log=log)
sm.quiesce_real_previews(source_nodes, log=log)
shared = group_nodes[0]

folder1 = rvc.newNode("RVFolderGroup", "")
rve.setUIName(folder1, "FolderOne")
rvc.setNodeInputs(folder1, [shared])

folder2 = rvc.newNode("RVFolderGroup", "")
rve.setUIName(folder2, "FolderTwo")
rvc.setNodeInputs(folder2, [shared])

log("folder1 inputs:", rvc.nodeConnections(folder1, False)[0])
log("folder2 inputs:", rvc.nodeConnections(folder2, False)[0])
log("shared node outputs:", rvc.nodeConnections(shared, False)[1])

# --- 2. Open panel, select SharedMedia's row specifically under FolderOne -----
panel = sm.open_session_manager_panel(log=log)
tree_view = sm.find_view_tree(panel)
folder1_index = sm.find_index_by_text(tree_view, "FolderOne")
tree_view.expand(folder1_index)
shared_under_folder1 = sm.find_child_index_by_node(tree_view, folder1_index, shared)
sm.select_index(tree_view, shared_under_folder1)

# --- 3. Click the real deleteButton --------------------------------------------
delete_button = panel.findChild(QtWidgets.QToolButton, "deleteButton")
click_button(delete_button)

still_exists = rvc.nodeExists(shared)
folder1_inputs_after = rvc.nodeConnections(folder1, False)[0] if rvc.nodeExists(folder1) else []
folder2_inputs_after = rvc.nodeConnections(folder2, False)[0] if rvc.nodeExists(folder2) else []
log("shared node exists after delete:", still_exists)
log("folder1 inputs after:", folder1_inputs_after)
log("folder2 inputs after:", folder2_inputs_after)

if not still_exists:
    raise AssertionError("multi-parent delete wrongly called deleteNode (node is gone)")
if shared in folder1_inputs_after:
    raise AssertionError("shared node was NOT removed from FolderOne")
if shared not in folder2_inputs_after:
    raise AssertionError("shared node was wrongly also removed from FolderTwo")

# --- 4. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
