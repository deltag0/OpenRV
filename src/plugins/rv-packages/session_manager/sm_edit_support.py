#
# Shared helpers for session_manager edit-mode Python ports.
#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import os

import rv.commands as commands
import rv.qtutils as qtutils

try:
    from PySide6.QtCore import QFile
    from PySide6.QtUiTools import QUiLoader
    from PySide6.QtWidgets import QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import QFile
    from PySide2.QtUiTools import QUiLoader
    from PySide2.QtWidgets import QWidget

INT_MAX = 2147483647


def checkbox_to_int(state: int) -> int:
    """Map Qt checkbox state to 0/1 for RV int properties."""
    try:
        from PySide6.QtCore import Qt
    except ImportError:  # pragma: no cover
        from PySide2.QtCore import Qt
    return 1 if state == Qt.Checked else 0


def session_manager():
    try:
        state = commands.data()
        mgr = getattr(state, "sessionManager", None)
        if mgr is not None:
            return mgr
    except Exception:
        pass
    try:
        import session_manager as sm_mod

        return sm_mod.theMode()
    except Exception:
        return None


def aux_file_path(name: str) -> str:
    mgr = session_manager()
    if mgr is not None and hasattr(mgr, "auxFilePath"):
        return mgr.auxFilePath(name)
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    staged = os.path.join(
        os.path.dirname(os.path.dirname(pkg_dir)),
        "SupportFiles",
        "session_manager",
        name,
    )
    if os.path.isfile(staged):
        return staged
    return os.path.join(pkg_dir, name)


def load_ui_file(name: str, parent: QWidget | None = None) -> QWidget | None:
    if parent is None:
        parent = qtutils.sessionWindow()
    path = aux_file_path(name)
    ui_file = QFile(path)
    if not ui_file.open(QFile.ReadOnly):
        return None
    widget = QUiLoader().load(ui_file, parent)
    ui_file.close()
    return widget


def set_mode_active(mode_name: str, on: bool) -> None:
    try:
        if on:
            if not commands.isModeActive(mode_name):
                commands.activateMode(mode_name)
        elif commands.isModeActive(mode_name):
            commands.deactivateMode(mode_name)
    except Exception:
        pass


def set_modes_active(mode_names: list[str], on: bool) -> None:
    for name in mode_names:
        set_mode_active(name, on)


def editor_registered(mgr, name: str) -> bool:
    for editor in getattr(mgr, "_editors", []):
        try:
            if editor.text(0) == name:
                return True
        except RuntimeError:
            continue
    return False


def ensure_editor(mgr, name: str, widget) -> bool:
    """Register an edit-tab widget once the session_manager panel exists."""
    if mgr is None or not getattr(mgr, "_panel_alive", lambda: False)():
        return False
    if editor_registered(mgr, name):
        return True
    mgr.addEditor(name, widget)
    return editor_registered(mgr, name)


def restore_edit_tab(mgr) -> None:
    if hasattr(mgr, "_restore_tab_state"):
        try:
            mgr._restore_tab_state()
        except RuntimeError:
            pass
    elif hasattr(mgr, "_tab_widget_ref"):
        tab = mgr._tab_widget_ref()
        if tab is not None:
            try:
                tab.setCurrentIndex(1)
            except RuntimeError:
                pass
