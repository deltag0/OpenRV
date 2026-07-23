"""Scenario: real `inputsDeleteButton` click removes a selected Inputs-tab
entry (COVERAGE §E5 -- the real UI trigger, closing the "button not" gap
left by `sm_inputs_delete`).

`inputsDeleteSlot` (session_manager.mu.in:3022) reads the Inputs-tab
selection and calls `setInputs` with that row excluded. Builds a real-media
RVStackGroup [MediaA, MediaB, MediaC], selects MediaB in the Inputs tab,
clicks the real `inputsDeleteButton`, and pins the resulting `[MediaA,
MediaC]` order.
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


# --- 1. Real-media sources, quiesced -------------------------------------------
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE, sm.IMAGE_FIXTURE], log=log
)
for grp, name in zip(group_nodes, ["MediaA", "MediaB", "MediaC"]):
    rve.setUIName(grp, name)
sm.quiesce_real_previews(source_nodes, log=log)

stack = rvc.newNode("RVStackGroup", "")
rvc.setNodeInputs(stack, group_nodes)
rvc.setViewNode(stack)
log("inputs before delete:", rvc.nodeConnections(stack, False))

# --- 2. Open panel, switch to Inputs tab, select MediaB (row 1), click Delete
panel = sm.open_session_manager_panel(log=log)
sm.find_tab(panel, "Inputs")
inputs_view = panel.findChild(QtWidgets.QListView, "inputsViewList")
if inputs_view is None:
    raise AssertionError("inputsViewList not found")
sm.select_row_by_position(inputs_view, 1)  # MediaB -- source rows' text is
# blanked once previews are enabled (session_manager.mu.in:1512-1516), so
# position is used instead of select_row_by_text; see _sm_common docstring.

inputs_delete = panel.findChild(QtWidgets.QToolButton, "inputsDeleteButton")
click_button(inputs_delete)
log("inputs after real inputsDeleteButton click:", rvc.nodeConnections(stack, False))

# --- 3. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 4. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
