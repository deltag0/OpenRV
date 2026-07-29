"""Scenario: toggle Floating Selector (COVERAGE §C2).

Requires ``LAYER_EXR_FIXTURE``. Right-clicks the widget popup when RV exposes a
``QMenu``; otherwise falls back to ``writeSettings`` (logged in diag). Captures
viewport before/after plus ``session.rv``.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, _, _ = ls.setup_exr_layer_select(docked=True, log=log)
ls.grab_viewport_png(out_dir, "viewport_docked.png", log=log)

used_popup = ls.toggle_floating_via_popup(log=log)
log("toggle via popup menu:", used_popup)
assert ls.read_docked_setting(log=log) is False

ls.grab_viewport_png(out_dir, "viewport_floating.png", log=log)
ls.save_session(out_dir, log=log)
diag.close()
