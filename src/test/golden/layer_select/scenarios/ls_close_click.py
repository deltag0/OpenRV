"""Scenario: close-button click deactivates widget (COVERAGE §D2).

Requires ``LAYER_EXR_FIXTURE``. Clicks the close-button hover region.
"""

import os

import rv.commands as rvc

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.setup_exr_layer_select(docked=True, log=log)
assert rvc.isModeActive(ls.MODE_RUNTIME_NAME)

ls.grab_viewport_png(out_dir, "viewport_before_close.png", log=log)
ls.click_close_area(log=log)
pump_note = rvc.isModeActive(ls.MODE_RUNTIME_NAME)
log("LayerSelect still active after close click:", pump_note)

ls.grab_viewport_png(out_dir, "viewport_after_close.png", log=log)
ls.save_session(out_dir, log=log)
diag.close()
