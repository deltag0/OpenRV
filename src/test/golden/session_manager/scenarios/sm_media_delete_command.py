"""Scenario: real-media version of `sm_delete` (COVERAGE §I8, single-parent
branch), command-driven outcome pin.

Builds a real-media (not `movieproc`) RVStackGroup over two sources,
quiesces previews, then deletes it via `deleteNode` -- mirroring the
`deleteViewableSlot` single-parent branch (session_manager.mu.in:2755
-> `deleteNode(node)`) for real-media-backed nodes. The real *button*
trigger for this same branch is covered by `sm_media_delete_button.py`.

Behavioral end-state: the stack group is GONE, the two real-media source
groups remain.
"""

import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. Real-media sources, quiesced -------------------------------------------
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE], log=log
)
sm.quiesce_real_previews(source_nodes, log=log)

# --- 2. RVStackGroup over both, make it current --------------------------------
stack = rvc.newNode("RVStackGroup", "")
rvc.setNodeInputs(stack, group_nodes)
rvc.setViewNode(stack)
log("created stack:", stack, "inputs:", rvc.nodeConnections(stack, False)[0])

# --- 3. Delete the stack view node (the §I8 single-parent behavior) -----------
rvc.deleteNode(stack)
log("stack exists after delete:", rvc.nodeExists(stack))
log("source groups after delete:", rvc.nodesOfType("RVSourceGroup"))

# --- 4. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Pixel capture -----------------------------------------------------------
panel = sm.open_session_manager_panel(log=log)
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
