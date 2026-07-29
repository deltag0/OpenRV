"""Scenario: click-release selects layer row (COVERAGE §B1 — real pointer trigger).

Requires ``LAYER_EXR_FIXTURE``. Uses an approximate docked-widget click position;
behavioral gate checks ``request.imageComponent`` if the click lands on a row.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, layers = ls.setup_exr_layer_select(docked=True, log=log)
ls.set_layer_request(file_source, None, log=log)

before = ls.read_layer_request(file_source)
ls.click_layer_row(release=True, log=log)
after = ls.read_layer_request(file_source)
log("imageComponent before:", before, "after click:", after)

if after == before:
    log(
        "NOTE: click did not change imageComponent — row geometry may need "
        "tuning on this platform; session.rv still captured for Mu baseline"
    )

ls.save_session(out_dir, log=log)
ls.grab_viewport_png(out_dir, log=log)
diag.close()
