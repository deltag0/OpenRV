"""Scenario: drag floating widget (COVERAGE §C3, §D3).

Requires ``LAYER_EXR_FIXTURE``. Floating mode; drag via real pointer gesture.
"""

import os

import _ls_common as ls
from qt_scenario_utils import QtCore

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.setup_exr_layer_select(docked=False, log=log)
start = ls.floating_widget_point(log=log)
end = QtCore.QPoint(start.x() + 80, start.y() + 60)

ls.grab_viewport_png(out_dir, "viewport_before_drag.png", log=log)
ls.drag_on_gl_view(start, end, log=log)
ls.grab_viewport_png(out_dir, "viewport_after_drag.png", log=log)

ls.save_session(out_dir, log=log)
diag.close()
