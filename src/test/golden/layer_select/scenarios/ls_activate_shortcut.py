"""Scenario: activate via ``/`` shortcut (COVERAGE §A1 — real UI trigger).

Unlike ``ls_activate`` (``activateMode`` API), this exercises ``key-down--/``.
"""

import os

import rv.commands as rvc

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.add_movieproc_source(log=log)
ls.deactivate_layer_select(log=log)
ls.toggle_via_shortcut(log=log)

assert rvc.isModeActive(ls.MODE_RUNTIME_NAME), "LayerSelect not active after / shortcut"

ls.save_session(out_dir, log=log)
diag.close()
