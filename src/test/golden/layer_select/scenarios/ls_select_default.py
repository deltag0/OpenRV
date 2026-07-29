"""Scenario: select Default layer — clear ``request.imageComponent`` (COVERAGE §B2).

Requires ``LAYER_EXR_FIXTURE``. Sets a named layer then clears to ``[]``.

Captures behavioral gate only.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, layers = ls.add_layer_exr_source(log=log)
ls.activate_layer_select(log=log)

ls.set_layer_request(file_source, layers[0], log=log)
ls.set_layer_request(file_source, None, log=log)

got = ls.read_layer_request(file_source)
assert got == [], "Default should clear imageComponent, got %r" % got

ls.save_session(out_dir, log=log)
diag.close()
