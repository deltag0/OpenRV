"""Scenario: real `selectCurrentButton` click re-syncs tree selection to the
current view node (COVERAGE §I, new row -- see COVERAGE.md update).

`selectCurrentViewSlot` -> `selectViewableNode()` (session_manager.mu.in:1536)
does NOT change the current view; it selects that node's row in the tree.
Sets MediaB as the current view, deliberately selects MediaA's row instead,
clicks the real `selectCurrentButton`, and asserts the tree selection moves
back to MediaB while `viewNode()` is unchanged -- this is UI-selection state
only (not part of the session graph), so it is pixel/log-gated, not
behavioral.
"""

import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import QtWidgets, click_button, grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. Real-media sources, quiesced --------------------------------------------
# Rows are found by node-NAME role (_sm_common.NODE_NAME_ROLE), not display
# text: a source row's display text is blanked once a preview widget
# attaches (mirrors the Inputs-list blanking at session_manager.mu.in:
# 1512-1516; observed for the tree too, timing-dependent), and a rename via
# `extra_commands.setUIName` never reaches an already-built row's text
# either (no rebuild fires for a property write alone). Node identity is
# unaffected by either, and scenarios already have the exact node name.
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE], log=log
)
sm.quiesce_real_previews(source_nodes, log=log)

groupA, groupB = group_nodes
rvc.setViewNode(groupB)
log("current view:", rvc.viewNode())

# --- 2. Open panel, deliberately select MediaA's row (NOT the current view) --
panel = sm.open_session_manager_panel(log=log)
tree_view = sm.find_view_tree(panel)
sm.select_row_by_node(tree_view, groupA)
log("selected before click:",
    [i.data(sm.NODE_NAME_ROLE) for i in tree_view.selectionModel().selectedIndexes()])

# --- 3. Click the real selectCurrentButton -------------------------------------
select_current = panel.findChild(QtWidgets.QToolButton, "selectCurrentButton")
click_button(select_current)
selected_after = [i.data(sm.NODE_NAME_ROLE) for i in tree_view.selectionModel().selectedIndexes()]
log("selected after click:", selected_after)
log("current view still:", rvc.viewNode())
if groupB not in selected_after:
    raise AssertionError(
        f"selectCurrentButton did not move tree selection to the current view "
        f"node {groupB!r}; selection is {selected_after}"
    )

# --- 4. Behavioral capture (viewNode is unchanged by this button) -------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
