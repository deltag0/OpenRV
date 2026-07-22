#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.extra_commands as extra_commands
import rv.qtutils as qtutils
from rv import rvtypes

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QComboBox, QWidget

from sm_edit_support import ensure_editor, load_ui_file, session_manager, set_modes_active


class FolderGroupEditMode(rvtypes.MinorMode):
    _VIEW_MODES = {
        "switch": ["Switch_edit_mode"],
        "layout": ["LayoutGroup_edit_mode"],
        "stack": ["StackGroup_edit_mode"],
    }

    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._ui: QWidget | None = None
        self._view_type_combo: QComboBox | None = None
        self.init(
            "FolderGroup_edit_mode",
            None,
            [
                ("session-manager-load-ui", self._load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
            ],
            None,
        )

    def _activate_ui(self, on: bool) -> None:
        try:
            vtype = commands.getStringProperty("#RVFolderGroup.mode.viewType")[0]
        except Exception:
            vtype = "layout"
        modes = self._VIEW_MODES.get(vtype, ["LayoutGroup_edit_mode"])
        set_modes_active(modes, on)

    def _set_view_type(self, index: int) -> None:
        if self._view_type_combo is None:
            return
        try:
            current = commands.getStringProperty("#RVFolderGroup.mode.viewType")[0]
        except Exception:
            current = ""
        newtype = self._view_type_combo.itemData(index)
        if newtype is None:
            newtype = self._view_type_combo.itemText(index).lower()
        if str(newtype) == current:
            return
        self._activate_ui(False)
        commands.setStringProperty("#RVFolderGroup.mode.viewType", [str(newtype)], True)
        commands.redraw()
        self._activate_ui(True)
        mgr = session_manager()
        if mgr is not None:
            mgr.reloadEditorTab()

    def _update_ui(self) -> None:
        if self._ui is None or self._view_type_combo is None:
            return
        if commands.viewNode() is None:
            return
        try:
            vtype = commands.getStringProperty("#RVFolderGroup.mode.viewType")[0]
            index = {"switch": 0, "layout": 1, "stack": 2}.get(vtype, 1)
            self._view_type_combo.setCurrentIndex(index)
        except Exception:
            pass

    def _load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None or not mgr._panel_alive():
            event.reject()
            return
        if self._ui is None:
            self._ui = load_ui_file("folder.ui", qtutils.sessionWindow())
            if self._ui is None:
                event.reject()
                return
            self._view_type_combo = self._ui.findChild(QComboBox, "viewTypeCombo")
            if self._view_type_combo is not None:
                self._view_type_combo.clear()
                self._view_type_combo.addItem("Switch", "switch")
                self._view_type_combo.addItem("Layout", "layout")
                self._view_type_combo.addItem("Stack", "stack")
                self._view_type_combo.currentIndexChanged.connect(self._set_view_type)
        if not ensure_editor(mgr, "Folder View", self._ui):
            event.reject()
            return
        self._update_ui()
        mgr.useEditor("Folder View")
        event.reject()

    def _property_changed(self, event) -> None:
        parts = event.contents().split(".")
        if len(parts) >= 3 and parts[1] == "mode" and parts[2] == "viewType":
            self._update_ui()
        event.reject()

    def activate(self) -> None:
        self._activate_ui(True)

    def deactivate(self) -> None:
        self._activate_ui(False)


def createMode():
    return FolderGroupEditMode()
