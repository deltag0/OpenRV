"""Scenario: docked widget viewport capture (COVERAGE §A4, §B7, §C4).

Requires ``LAYER_EXR_FIXTURE``. Activates Layer Selector with a multi-layer
source as the current view and captures the GL viewport (layer list in margin).

Captures behavioral + ``viewport.png`` pixel gate.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, layers = ls.add_layer_exr_source(log=log)
log("layers:", layers)

ls.write_docked_setting(True, log=log)
ls.activate_layer_select(log=log)
ls.set_layer_request(file_source, layers[0], log=log)

ls.save_session(out_dir, log=log)
ls.grab_viewport_png(out_dir, log=log)

diag.close()
