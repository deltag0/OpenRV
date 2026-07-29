"""Scenario: deactivate via ``/`` shortcut toggle (COVERAGE §A1 off-path)."""

import os

import rv.commands as rvc

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.add_movieproc_source(log=log)
ls.activate_layer_select(log=log)
assert rvc.isModeActive(ls.MODE_RUNTIME_NAME)

ls.toggle_via_shortcut(log=log)
log("active after second /:", rvc.isModeActive(ls.MODE_RUNTIME_NAME))

ls.save_session(out_dir, log=log)
diag.close()
