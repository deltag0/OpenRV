"""Scenario: real `configButton` click opens the Config popup menu and
toggles "Show Source Previews" (COVERAGE §I, new row -- see COVERAGE.md
update).

`_configButton.setMenu(configMenu)` (session_manager.mu.in:3474); the
"Show Source Previews" action is a checkable toggle
(session_manager.mu.in:3464-3467) that isn't part of the session graph
(writeSetting, not a node property -- see the "settings persistence" item
in the Dropped list), so this is **pixel-only**: two PNG artifacts capture
the menu's checked-state before and after the click. Needs the compare.py
multi-PNG generalization (every `*.png` in the golden dir is compared, not
just `panel.png`).

This scenario passed cleanly on first run during macOS smoke-testing, then
hung intermittently on later re-runs -- see the note on
`qt_scenario_utils.open_tool_button_menu` (same InstantPopup mechanism as
the `folderButton` hang). Re-verify on a clean session / the Linux target
before trusting it.
"""

import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import QtWidgets, open_tool_button_menu, click_menu_action, grab_widget_png, pump

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. Open panel, open the real Config popup menu ----------------------------
panel = sm.open_session_manager_panel(log=log)
config_button = panel.findChild(QtWidgets.QToolButton, "configButton")
menu = open_tool_button_menu(config_button)
ok1, w1, h1 = grab_widget_png(menu, os.path.join(out_dir, "configmenu_before.png"))
log("configmenu_before.png saved:", ok1, w1, h1)

# --- 2. Click "Show Source Previews" (closes the menu) -------------------------
click_menu_action(menu, "Show Source Previews")

# --- 3. Reopen to capture the toggled checked-state ----------------------------
menu2 = open_tool_button_menu(config_button)
ok2, w2, h2 = grab_widget_png(menu2, os.path.join(out_dir, "configmenu_after.png"))
log("configmenu_after.png saved:", ok2, w2, h2)
menu2.close()
pump(200)

# --- 4. Behavioral capture (unaffected by this setting; kept for uniformity) --
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Standard panel screenshot -----------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
