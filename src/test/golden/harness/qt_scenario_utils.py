#
# Shared Qt helpers for in-RV golden scenarios (package-agnostic).
#
# Every scenario needs the same handful of things: a Qt binding that works on
# both Qt5 and Qt6 builds, a way to pump the event loop (``-pyeval`` runs
# before QCoreApplication::exec(), so nothing paints on its own), and now a
# way to drive *real* widgets with synthetic input instead of calling the
# command each widget is wired to. Plain clicks (QTest.mouseClick) are not
# subject to the drag/drop limitation documented in COVERAGE.md section G
# (synthesized QDropEvents have a null source()) -- only the drag *gesture*
# is blocked headlessly, so button/menu clicks are a genuine way to exercise
# the real UI trigger rather than just pinning its outcome.
#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import time

try:
    from PySide6 import QtWidgets, QtCore, QtTest
    import shiboken6 as shiboken  # noqa: F401  (parity with existing scenarios)

    QTest = QtTest.QTest
except ImportError:  # pragma: no cover - older Qt
    from PySide2 import QtWidgets, QtCore, QtTest
    import shiboken2 as shiboken  # noqa: F401

    QTest = QtTest.QTest


def pump(ms: int) -> None:
    """Pump the Qt event loop for ~ms without a bare sleep."""
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


def click_button(button, settle_ms: int = 300) -> None:
    """Synthesize a real left-click on a QAbstractButton (or subclass).

    Fails loudly on a missing/hidden/disabled target rather than silently
    no-op'ing -- a scenario that can't find the real widget must not report
    a pass, since that would mean the button was never actually exercised.
    """
    if button is None:
        raise AssertionError("click_button: target widget is None")
    if not button.isVisible():
        raise AssertionError(f"click_button: {button.objectName()!r} is not visible")
    if not button.isEnabled():
        raise AssertionError(f"click_button: {button.objectName()!r} is not enabled")
    QTest.mouseClick(button, QtCore.Qt.LeftButton)
    pump(settle_ms)


def open_tool_button_menu(button, settle_ms: int = 300):
    """Click a QToolButton wired via setMenu()/InstantPopup and return its QMenu.

    Raises if the button has no menu attached -- that's a wiring change the
    scenario must catch, not silently skip.

    OPEN ISSUE (macOS smoke-testing only): the underlying `click_button()`
    call was observed to hang indefinitely for `folderButton` and, once,
    intermittently for `configButton` -- both InstantPopup buttons, same
    wiring as `addButton`, which never hung. The pattern (first run clean,
    later runs hanging after this process had force-killed a prior hung `rv`
    instance) points at leftover macOS WindowServer/NSMenu tracking state
    from those kills rather than a deterministic scenario bug, but this is
    UNPROVEN. Re-verify on a clean session and, ideally, directly on the
    pinned Linux + Xvfb target (a fresh X server per run, unaffected by host
    state) before trusting or dropping the affected scenarios.
    """
    menu = button.menu() if button is not None else None
    if menu is None:
        name = button.objectName() if button is not None else "<None>"
        raise AssertionError(f"open_tool_button_menu: {name!r} has no menu() attached")
    click_button(button, settle_ms=settle_ms)
    return menu


def click_menu_action(menu, text: str, settle_ms: int = 250) -> None:
    """Click the QAction in ``menu`` whose (accelerator-stripped) text matches.

    Raises if not found, listing available actions -- a renamed/removed menu
    item must break the scenario, not vanish quietly.
    """
    if menu is None:
        raise AssertionError("click_menu_action: menu is None")
    pump(settle_ms)
    target = None
    for action in menu.actions():
        if action.text().replace("&", "") == text:
            target = action
            break
    if target is None:
        available = [a.text() for a in menu.actions()]
        raise AssertionError(
            f"click_menu_action: no action {text!r} found; available: {available}"
        )
    rect = menu.actionGeometry(target)
    QTest.mouseClick(menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
    pump(settle_ms)


def grab_widget_png(widget, path: str, settle_ms: int = 400):
    """Pump, grab ``widget`` to a PNG, and return (ok, width, height).

    Raises if the save fails outright (bad path etc.); a False ``ok`` from
    QPixmap.save is still returned to the caller to log, since a 0x0 grab is
    a real signal something's wrong with the widget, not a harness bug.
    """
    if widget is None:
        raise AssertionError("grab_widget_png: widget is None")
    if not widget.isVisible():
        widget.show()
    pump(settle_ms)
    pixmap = widget.grab()
    ok = pixmap.save(path, "PNG")
    return ok, pixmap.width(), pixmap.height()
