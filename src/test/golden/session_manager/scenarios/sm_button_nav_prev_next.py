"""Scenario: real `prevViewButton`/`nextViewButton` clicks walk view history
(COVERAGE §D4 -- the real UI trigger, closing the "button not" gap left by
`sm_nav`).

`navButtonClicked` (session_manager.mu.in:3085) calls `setViewNode` on
`previous/nextViewNode()`, which walk view *history* (back/forward), not
`viewNodes()` (see COVERAGE.md port notes). Media-free `movieproc` sources
are used deliberately here (per VERIFICATION.md's determinism table:
"use media-free fixtures where possible") since nav history is independent
of media type and this keeps the pixel gate off the still-unproven real
thumbnail determinism.

Builds two sources, makes B the current view (so A is history), clicks the
real `prevViewButton` (expect A), then the real `nextViewButton` (expect B
again).
"""

import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import QtWidgets, click_button, grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. Two media-free sources; B becomes current (A is history) -------------
srcA = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
groupA = rvc.nodeGroup(srcA)
rvc.setViewNode(groupA)

srcB = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
groupB = rvc.nodeGroup(srcB)
rvc.setViewNode(groupB)
sm.quiesce_real_previews([srcA, srcB], log=log)
log("current view:", rvc.viewNode(), "previousViewNode:", rvc.previousViewNode())

# --- 2. Open panel, click real prevViewButton -> expect A ----------------------
# prevViewButton/nextViewButton live in a navPanel parented directly to the
# dock widget, not under the `panel` content widget -- sm.find_button()
# falls back to a window-wide search for exactly this case.
panel = sm.open_session_manager_panel(log=log)
prev_button = sm.find_button(panel, "prevViewButton")
click_button(prev_button)
after_prev = rvc.viewNode()
log("view after real prevViewButton click:", after_prev)
if after_prev != groupA:
    raise AssertionError(f"expected viewNode {groupA!r} after Prev, got {after_prev!r}")

# --- 3. Click real nextViewButton -> expect B again ----------------------------
next_button = sm.find_button(panel, "nextViewButton")
click_button(next_button)
after_next = rvc.viewNode()
log("view after real nextViewButton click:", after_next)
if after_next != groupB:
    raise AssertionError(f"expected viewNode {groupB!r} after Next, got {after_next!r}")

# --- 4. Behavioral capture (final state: B current again) ---------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
