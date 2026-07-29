"""Scenario: stylus pen select layer row (COVERAGE §D1).

Requires ``LAYER_EXR_FIXTURE``. Sends stylus-pen push/move/release on the widget.
"""

import os

import rv.commands as rvc

import _ls_common as ls

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, layers = ls.setup_exr_layer_select(docked=True, log=log)
ls.set_layer_request(file_source, None, log=log)

pt = ls.docked_widget_point(log=log)
ls.move_pointer_on_gl_view(pt, log=log)
ls.send_stylus_press(log=log)
ls.send_stylus_move(log=log)
ls.send_stylus_release(log=log)

got = ls.read_layer_request(file_source)
log("imageComponent after stylus release:", got, "layers:", layers)

ls.save_session(out_dir, log=log)
ls.grab_viewport_png(out_dir, log=log)
diag.close()
