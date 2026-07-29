"""Scenario: close-button hover chrome (COVERAGE §D2).

Requires ``LAYER_EXR_FIXTURE``. Moves pointer near the widget top-left close area.
"""

import os

import _ls_common as ls
import rv.commands as rvc
from qt_scenario_utils import QtCore

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.setup_exr_layer_select(docked=True, log=log)

base = ls.docked_widget_point(log=log)
try:
    margin = int(rvc.data().config.bevelMargin)
except Exception:
    margin = 8

close_pt = QtCore.QPoint(max(4, base.x() - margin), max(4, base.y() - margin * 2))
log("close hover point:", close_pt.x(), close_pt.y())

ls.grab_viewport_png(out_dir, "viewport_before_close.png", log=log)
ls.move_pointer_on_gl_view(close_pt, log=log)
ls.grab_viewport_png(out_dir, "viewport_close_hover.png", log=log)

ls.save_session(out_dir, log=log)
diag.close()
