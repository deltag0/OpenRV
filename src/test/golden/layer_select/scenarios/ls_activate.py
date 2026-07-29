"""Scenario: activate Layer Selector (COVERAGE §A1, §A3).

Loads movieproc, activates ``layer_select_mode`` / ``LayerSelect``, and saves
session state. No real media required.

Captures behavioral gate only (``session.rv``).
"""

import os

import rv.commands as rvc

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.add_movieproc_source(log=log)
ls.activate_layer_select(log=log)

assert rvc.isModeActive(ls.MODE_RUNTIME_NAME), "LayerSelect mode not active"

ls.save_session(out_dir, log=log)
diag.close()
