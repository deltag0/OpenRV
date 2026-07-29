"""Scenario: hover updates highlight (COVERAGE §B5, §B6).

Requires ``LAYER_EXR_FIXTURE``. Moves pointer over the widget then away; pixel
gate compares before/inside/outside viewport captures.
"""

import os

import _ls_common as ls
from qt_scenario_utils import QtCore

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


_, _, file_source, layers = ls.setup_exr_layer_select(docked=True, log=log)
ls.set_layer_request(file_source, layers[0], log=log)
log("active layer:", layers[0])

ls.grab_viewport_png(out_dir, "viewport_before_hover.png", log=log)
ls.move_pointer_on_gl_view(ls.docked_widget_point(log=log), log=log)
ls.grab_viewport_png(out_dir, "viewport_hover_widget.png", log=log)

vs = ls.gl_view().size()
away = QtCore.QPoint(vs.width() - 40, vs.height() - 40)
ls.move_pointer_on_gl_view(away, log=log)
ls.grab_viewport_png(out_dir, "viewport_after_leave.png", log=log)

ls.save_session(out_dir, log=log)
diag.close()
