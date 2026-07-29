"""Scenario: floating widget layout (COVERAGE §C3, §D3).

Requires ``LAYER_EXR_FIXTURE``. Sets floating mode via settings (same outcome as
``optFloatingSelector`` when starting from docked) and captures viewport pixels.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.setup_exr_layer_select(docked=False, log=log)
ls.grab_viewport_png(out_dir, log=log)
ls.save_session(out_dir, log=log)
diag.close()
