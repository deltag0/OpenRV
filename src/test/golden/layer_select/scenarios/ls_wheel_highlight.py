"""Scenario: wheel moves highlight without commit (COVERAGE §B4).

Requires ``LAYER_EXR_FIXTURE``. Captures viewport before/after wheel-down events
(pixel gate on highlight marker movement).
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, layers = ls.setup_exr_layer_select(docked=True, log=log)
ls.set_layer_request(file_source, None, log=log)
log("layers:", layers)

ls.grab_viewport_png(out_dir, "viewport_before_wheel.png", log=log)
ls.send_wheel_down(2, log=log)
ls.grab_viewport_png(out_dir, "viewport_after_wheel.png", log=log)

# Wheel must not commit — request stays default.
assert ls.read_layer_request(file_source) == [], "wheel should not commit layer"

ls.save_session(out_dir, log=log)
diag.close()
