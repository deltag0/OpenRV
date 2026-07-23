"""Scenario: real `orderDownButton` click reorders real-media Inputs entries
(COVERAGE §E3 -- the real UI trigger, closing the "button not" gap left by
`sm_inputs_reorder`/`sm_media_reorder_command`).

`orderUpButton`/`orderDownButton` give a genuine, non-drag, headlessly
clickable way to reorder Inputs-tab rows -- this sidesteps the drag/drop
limitation in COVERAGE.md section G entirely (`reorderSelected`,
session_manager.mu.in:2806, is driven by a plain QAction, not a drag).

Builds a real-media RVStackGroup [MediaA, MediaB, MediaC], selects MediaA in
the Inputs tab, clicks the real `orderDownButton`, and pins the resulting
order via `setInputs`'s outcome (behavioral) plus the panel appearance
(pixel).
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


# --- 1. Real-media sources in SORTED order [A, B, C] --------------------------
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE, sm.IMAGE_FIXTURE], log=log
)
for grp, name in zip(group_nodes, ["MediaA", "MediaB", "MediaC"]):
    rve.setUIName(grp, name)
sm.quiesce_real_previews(source_nodes, log=log)

stack = rvc.newNode("RVStackGroup", "")
rvc.setNodeInputs(stack, group_nodes)
rvc.setViewNode(stack)
log("inputs before reorder:", rvc.nodeConnections(stack, False))

# --- 2. Open panel, switch to Inputs tab, select MediaA (row 0), click Order Down
panel = sm.open_session_manager_panel(log=log)
sm.find_tab(panel, "Inputs")
inputs_view = panel.findChild(QtWidgets.QListView, "inputsViewList")
if inputs_view is None:
    raise AssertionError("inputsViewList not found")
sm.select_row_by_position(inputs_view, 0)  # MediaA -- source rows' text is
# blanked once previews are enabled (session_manager.mu.in:1512-1516), so
# position is used instead of select_row_by_text; see _sm_common docstring.

order_down = panel.findChild(QtWidgets.QToolButton, "orderDownButton")
click_button(order_down)
log("inputs after real orderDownButton click:", rvc.nodeConnections(stack, False))

# --- 3. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 4. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
