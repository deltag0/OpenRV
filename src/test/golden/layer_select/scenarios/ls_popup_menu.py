"""Scenario: capture floating-selector popup menu pixels (COVERAGE §C2 menu chrome).

Requires ``LAYER_EXR_FIXTURE``. Right-click popup; grabs menu widget if RV exposes it.
"""

import os

import _ls_common as ls
from qt_scenario_utils import QtWidgets, grab_widget_png, pump

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


ls.setup_exr_layer_select(docked=True, log=log)
menu = ls.right_click_on_gl_view(log=log)
if menu is not None:
    ok, w, h = grab_widget_png(menu, os.path.join(out_dir, "layer_popup.png"))
    log("layer_popup.png:", ok, w, h)
    menu.close()
    pump(200)
else:
    log("no QMenu captured — Mu popup may not be a Qt widget on this build")

ls.save_session(out_dir, log=log)
ls.grab_viewport_png(out_dir, log=log)
diag.close()
