"""Scenario: real-media version of `sm_inputs_reorder` (COVERAGE §E3).

Same NON-sorted-order pin as `sm_inputs_reorder`, but with real-file-backed
source groups (image, movie, image) instead of `movieproc`, quiesced before
capture -- proves the behavioral gate (`setNodeInputs` order) holds for real
media, not just synthetic sources. The real *button* trigger is covered
separately by `sm_media_reorder_button.py`.

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png
"""

import os

import rv.commands as rvc
import rv.extra_commands as rve

import _sm_common as sm
from qt_scenario_utils import grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. Real-media sources, quiesced, THEN given distinct UI names for readability
# (setUIName after quiesce -- see _sm_common.quiesce_real_previews docstring)
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE, sm.IMAGE_FIXTURE], log=log
)
sm.quiesce_real_previews(source_nodes, log=log)
for grp, name in zip(group_nodes, ["MediaA", "MediaB", "MediaC"]):
    rve.setUIName(grp, name)

# --- 2. RVStackGroup wired in a deliberately NON-sorted order [C, A, B] -------
srcA, srcB, srcC = group_nodes
reordered = [srcC, srcA, srcB]
stack = rvc.newNode("RVStackGroup", "")
rvc.setNodeInputs(stack, reordered)
rvc.setViewNode(stack)
log("stack inputs after setNodeInputs:", rvc.nodeConnections(stack, False))

# --- 3. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 4. Pixel capture -----------------------------------------------------------
panel = sm.open_session_manager_panel(log=log)
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
