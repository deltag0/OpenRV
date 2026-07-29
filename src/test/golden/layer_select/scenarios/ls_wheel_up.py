"""Scenario: wheel up moves highlight (COVERAGE §B4 both directions).

Requires ``LAYER_EXR_FIXTURE``. Wheel down then wheel up; highlight must not commit.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, _ = ls.setup_exr_layer_select(docked=True, log=log)
ls.set_layer_request(file_source, None, log=log)

ls.grab_viewport_png(out_dir, "viewport_before_wheel.png", log=log)
ls.send_wheel_down(2, log=log)
ls.grab_viewport_png(out_dir, "viewport_after_wheel_down.png", log=log)
ls.send_wheel_up(2, log=log)
ls.grab_viewport_png(out_dir, "viewport_after_wheel_up.png", log=log)

assert ls.read_layer_request(file_source) == []

ls.save_session(out_dir, log=log)
diag.close()
