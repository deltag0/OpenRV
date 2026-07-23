"""Scenario: real `sortAscButton`/`sortDescButton` clicks sort a real-media
Inputs list by name (COVERAGE §E4 -- the real UI trigger, closing the
"button not" gap left by `sm_inputs_sort`).

`sortInputs(up)` (session_manager.mu.in:2871) sorts `nodeInputs(viewNode())`
by `uiName`, ascending or descending, via `setInputs` -- no selection is
needed (unlike reorder/delete). Builds a real-media RVStackGroup with inputs
deliberately out of alphabetical order (Charlie, Alpha, Bravo), clicks the
real `sortAscButton` (expect Alpha, Bravo, Charlie), then the real
`sortDescButton` (expect Charlie, Bravo, Alpha), pinning both outcomes.
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


# --- 1. Real-media sources, quiesced, THEN given deliberately unsorted UI names
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE, sm.IMAGE_FIXTURE], log=log
)
sm.quiesce_real_previews(source_nodes, log=log)
names = ["Charlie", "Alpha", "Bravo"]
for grp, name in zip(group_nodes, names):
    rve.setUIName(grp, name)

stack = rvc.newNode("RVStackGroup", "")
rvc.setNodeInputs(stack, group_nodes)  # [Charlie, Alpha, Bravo]
rvc.setViewNode(stack)
log("inputs before sort:", [rve.uiName(n) for n in rvc.nodeConnections(stack, False)[0]])

panel = sm.open_session_manager_panel(log=log)
sm.find_tab(panel, "Inputs")

# --- 2. Click the real sortAscButton -> expect [Alpha, Bravo, Charlie] --------
sort_asc = panel.findChild(QtWidgets.QToolButton, "sortAscButton")
click_button(sort_asc)
after_asc = [rve.uiName(n) for n in rvc.nodeConnections(stack, False)[0]]
log("inputs after real sortAscButton click:", after_asc)
if after_asc != ["Alpha", "Bravo", "Charlie"]:
    raise AssertionError(f"expected ascending sort, got {after_asc}")

# --- 3. Click the real sortDescButton -> expect [Charlie, Bravo, Alpha] -------
sort_desc = panel.findChild(QtWidgets.QToolButton, "sortDescButton")
click_button(sort_desc)
after_desc = [rve.uiName(n) for n in rvc.nodeConnections(stack, False)[0]]
log("inputs after real sortDescButton click:", after_desc)
if after_desc != ["Charlie", "Bravo", "Alpha"]:
    raise AssertionError(f"expected descending sort, got {after_desc}")

# --- 4. Behavioral capture (final state: descending) ---------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
