"""Scenario: movieproc source — widget with no layer list (COVERAGE §A5).

Multi-layer list is empty for movieproc; widget should not show layer rows.

Captures behavioral + viewport pixel gate.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.add_movieproc_source(log=log)
ls.activate_layer_select(log=log)

ls.save_session(out_dir, log=log)
ls.grab_viewport_png(out_dir, log=log)

diag.close()
