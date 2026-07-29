"""Scenario: Tools/Layer Selector menu activates mode (COVERAGE §A2)."""

import os

import rv.commands as rvc

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.add_movieproc_source(log=log)
ls.deactivate_layer_select(log=log)
ls.activate_via_tools_menu(log=log)

assert rvc.isModeActive(ls.MODE_RUNTIME_NAME), "LayerSelect not active after menu"

ls.save_session(out_dir, log=log)
diag.close()
