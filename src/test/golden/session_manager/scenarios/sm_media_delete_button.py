"""Scenario: real `deleteButton` click deletes a real-media view node
(COVERAGE §I8, single-parent branch -- the real UI trigger).

`deleteViewableSlot` (session_manager.mu.in:2755) reads `selectedItems()`
from the tree view, not the current view node, so this selects the target
node's row in the tree directly (by its UI name -- generic, works against
either implementation) rather than relying on setViewNode.

Behavioral end-state: the stack group is GONE, the two real-media source
groups remain -- proves the real button reaches the same `deleteNode` path
`sm_media_delete_command.py` pins directly.
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


# --- 1. Real-media sources under a stack, quiesced -----------------------------
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE], log=log
)
sm.quiesce_real_previews(source_nodes, log=log)

stack = rvc.newNode("RVStackGroup", "")
rvc.setNodeInputs(stack, group_nodes)
rve.setUIName(stack, "MediaStack")
rvc.setViewNode(stack)
log("created stack:", stack)

# --- 2. Open panel, select the stack's row in the tree, click Delete ----------
panel = sm.open_session_manager_panel(log=log)
tree_view = sm.find_view_tree(panel)
sm.select_row_by_text(tree_view, "MediaStack")

delete_button = panel.findChild(QtWidgets.QToolButton, "deleteButton")
click_button(delete_button)
log("stack exists after real deleteButton click:", rvc.nodeExists(stack))
log("source groups remaining:", rvc.nodesOfType("RVSourceGroup"))

# --- 3. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 4. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
