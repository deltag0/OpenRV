#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
import rv.rvtypes as rvtypes

from sm_edit_support import load_ui_file, session_manager, set_modes_active

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QComboBox, QWidget

g_the_mode = None


class FolderGroupEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._ui = None
        self._view_type_combo: QComboBox | None = None

        self.init(
            "FolderGroup_edit_mode",
            None,
            [
                ("session-manager-load-ui", self.load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            None,
            None,
        )

    def _child_modes(self) -> list[str]:
        try:
            current_type = commands.getStringProperty("#RVFolderGroup.mode.viewType")[0]
        except Exception:
            current_type = "layout"

        if current_type == "switch":
            return ["Switch_edit_mode"]
        if current_type == "stack":
            return ["StackGroup_edit_mode"]
        if current_type == "layout":
            return ["LayoutGroup_edit_mode"]
        return ["LayoutGroup_edit_mode"]

    def _activate_ui(self, on: bool) -> None:
        set_modes_active(self._child_modes(), on)

    def set_view_type(self, index: int) -> None:
        if self._view_type_combo is None:
            return

        try:
            current_type = commands.getStringProperty("#RVFolderGroup.mode.viewType")[0]
        except Exception:
            current_type = ""

        new_type = self._view_type_combo.itemData(index, Qt.UserRole)
        if new_type is None:
            new_type = self._view_type_combo.itemText(index)

        if new_type != current_type:
            self._activate_ui(False)
            commands.set("#RVFolderGroup.mode.viewType", new_type)
            commands.redraw()
            self._activate_ui(True)

            mgr = session_manager()
            if mgr is not None and hasattr(mgr, "reloadEditorTab"):
                mgr.reloadEditorTab()

    def update_ui(self) -> None:
        if self._ui is None:
            return

        vnode = commands.viewNode()
        if vnode is None:
            return

        try:
            view_type = commands.getStringProperty("#RVFolderGroup.mode.viewType")[0]
            index_map = {"switch": 0, "layout": 1, "stack": 2}
            index = index_map.get(view_type, 1)
            if self._view_type_combo is not None:
                self._view_type_combo.setCurrentIndex(index)
        except Exception:
            pass

    def load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None:
            event.reject()
            return

        parent = qtutils.sessionWindow()

        if self._ui is None:
            self._ui = load_ui_file("folder.ui", parent)
            if self._ui is None:
                event.reject()
                return

            self._view_type_combo = self._ui.findChild(QComboBox, "viewTypeCombo")
            if self._view_type_combo is not None:
                self._view_type_combo.clear()
                self._view_type_combo.addItem("Switch", "switch")
                self._view_type_combo.addItem("Layout", "layout")
                self._view_type_combo.addItem("Stack", "stack")
                self._view_type_combo.currentIndexChanged.connect(self.set_view_type)

            mgr.addEditor("Folder View", self._ui)

        self.update_ui()
        mgr.useEditor("Folder View")
        event.reject()

    def activate(self) -> None:
        self._activate_ui(True)

    def deactivate(self) -> None:
        self._activate_ui(False)

    def property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) >= 3 and parts[1] == "mode" and parts[2] == "viewType":
            self.update_ui()
        event.reject()


def createMode():
    global g_the_mode
    g_the_mode = FolderGroupEditMode()
    return g_the_mode
