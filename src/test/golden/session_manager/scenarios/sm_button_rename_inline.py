"""Scenario: real `renameButton` click opens inline tree edit and commits a
new name (COVERAGE §I7 -- the real UI trigger, closing the "inline-edit
trigger not" gap left by `sm_rename`).

NOTE: highest-risk scenario in this batch (per the coverage-closing plan).
The `renameButton` widget is `_editViewInfoButton` in code (see
session_manager.mu.in:3202, `_baseWidget.findChild("renameButton")`) and
triggers `editViewInfoSlot` -> `_viewTreeView.edit(index)` (line 2798-2804),
which opens an in-place `QLineEdit` editor Qt creates on demand (the item's
`setEditable(true)`, line 1947, makes this possible). Committing that editor
fires `viewItemChanged` -> `setUIName(node, item.text())` (line ~1455). If
this proves unreliable headlessly, leave §I7 at 🟡 with this scenario noted
as the attempted-but-flaky trigger, per VERIFICATION.md's DoD rule 3 (no
silent 🟡 without recorded justification) -- do not loosen the assertion to
force a pass.

Media-free (movieproc) source: renaming is independent of media type.
"""

import os

import rv.commands as rvc
import rv.extra_commands as rve

import _sm_common as sm
from qt_scenario_utils import QtWidgets, QtCore, QTest, click_button, grab_widget_png, pump

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


# --- 1. One media-free source -----------------------------------------------
src = rvc.addSourceVerbose(["smptebars,start=1,end=24,fps=24.movieproc"])
group = rvc.nodeGroup(src)
log("initial uiName:", rve.uiName(group))

# --- 2. Open panel, select the row in the tree (by node identity -- see
# sm_button_select_current.py for why display text can't be used here: the
# row is already built with its default name by the time addSourceVerbose
# returns) ---------------------------------------------------------------
panel = sm.open_session_manager_panel(log=log)
tree_view = sm.find_view_tree(panel)
index = sm.select_row_by_node(tree_view, group)

# --- 3. Click the real renameButton -> expect an inline QLineEdit editor -----
rename_button = panel.findChild(QtWidgets.QToolButton, "renameButton")
click_button(rename_button)
pump(300)
editor = tree_view.findChild(QtWidgets.QLineEdit)
if editor is None:
    raise AssertionError(
        "renameButton click did not open an inline QLineEdit editor "
        "(see docstring: may need to stay COVERAGE §I7 = \U0001F7E1)"
    )

# --- 4. Type a new name and commit ---------------------------------------------
editor.selectAll()
QTest.keyClicks(editor, "NewMediaName")
QTest.keyClick(editor, QtCore.Qt.Key_Return)
pump(300)

renamed = rve.uiName(group)
log("uiName after inline rename commit:", renamed)
if renamed != "NewMediaName":
    raise AssertionError(f"expected uiName 'NewMediaName', got {renamed!r}")

# --- 5. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 6. Pixel capture -----------------------------------------------------------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
