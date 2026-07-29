"""Scenario: select a named layer via ``request.imageComponent`` (COVERAGE §B1).

Pins the graph outcome of ``LayerSelect.setSelectedLayer``: after choosing a
layer, ``<RVFileSource>.request.imageComponent = ["layer", "", <name>]``.

Requires ``LAYER_EXR_FIXTURE`` (multi-layer EXR). Real click not exercised.

Captures behavioral gate only.
"""

import os

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, layers = ls.add_layer_exr_source(log=log)
layer_name = ls.named_layers(layers)[0]
log("selecting layer:", layer_name)

ls.activate_layer_select(log=log)
ls.set_layer_request(file_source, layer_name, log=log)

got = ls.read_layer_request(file_source)
assert got == ["layer", "", layer_name], "unexpected imageComponent: %r" % got

ls.save_session(out_dir, log=log)
diag.close()
