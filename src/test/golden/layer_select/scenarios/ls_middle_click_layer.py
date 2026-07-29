"""Scenario: middle-click commits highlighted layer (COVERAGE §B3).

Requires ``LAYER_EXR_FIXTURE``. Wheel to move highlight, then ``pointer-2--push``.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, layers = ls.setup_exr_layer_select(docked=True, log=log)
ls.set_layer_request(file_source, None, log=log)

ls.send_wheel_down(1, log=log)
ls.send_middle_click(log=log)

got = ls.read_layer_request(file_source)
log("imageComponent after middle click:", got)
# Headless runs may not populate pixelInfo for wheel highlight; session.rv is the gate.

ls.save_session(out_dir, log=log)
diag.close()
