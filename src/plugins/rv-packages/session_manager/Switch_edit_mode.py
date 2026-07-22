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
    from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QCheckBox, QComboBox, QLineEdit, QWidget

from sm_edit_support import checkbox_to_int, ensure_editor, load_ui_file, session_manager


class SwitchEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._ui: QWidget | None = None
        self._ui_in_flux = False
        self._align_check: QCheckBox | None = None
        self._use_cut_check: QCheckBox | None = None
        self._auto_size_check: QCheckBox | None = None
        self._selected_combo: QComboBox | None = None
        self._width_edit: QLineEdit | None = None
        self._height_edit: QLineEdit | None = None
        self.init(
            "Switch_edit_mode",
            None,
            [
                ("session-manager-load-ui", self._load_ui, "Load UI into Session Manager"),
                ("range-changed", self._update_ui_event, "Update UI"),
                ("image-structure-change", self._update_ui_event, "Update UI"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
            ],
            None,
            "z0",
        )

    def _check_box_slot(self, state: int, prop: str) -> None:
        commands.setIntProperty(prop, [checkbox_to_int(state)], True)

    def _update_ui(self) -> None:
        if self._ui is None or commands.viewNode() is None:
            return
        self._ui_in_flux = True
        try:
            a = commands.getIntProperty("#RVSwitch.mode.alignStartFrames")[0]
            u = commands.getIntProperty("#RVSwitch.mode.useCutInfo")[0]
            c = commands.getStringProperty("#RVSwitch.output.input")[0]
            asize = commands.getIntProperty("#RVSwitch.output.autoSize")[0]
            size = commands.getIntProperty("#RVSwitch.output.size")
            if self._align_check is not None:
                self._align_check.setCheckState(Qt.Checked if a else Qt.Unchecked)
            if self._use_cut_check is not None:
                self._use_cut_check.setCheckState(Qt.Checked if u else Qt.Unchecked)
            if self._auto_size_check is not None:
                self._auto_size_check.setCheckState(Qt.Checked if asize else Qt.Unchecked)
            if self._selected_combo is not None:
                self._selected_combo.clear()
                inputs = commands.nodeConnections(commands.viewNode(), False)[0]
                selected = 0
                for i, inp in enumerate(inputs):
                    self._selected_combo.addItem(extra_commands.uiName(inp), inp)
                    if inp == c:
                        selected = i
                self._selected_combo.setCurrentIndex(selected)
            if self._width_edit is not None:
                self._width_edit.setEnabled(asize == 0)
                self._width_edit.setText(str(size[0]))
            if self._height_edit is not None:
                self._height_edit.setEnabled(asize == 0)
                self._height_edit.setText(str(size[1]))
        except Exception:
            pass
        commands.redraw()
        self._ui_in_flux = False

    def _update_ui_event(self, event) -> None:
        event.reject()
        self._update_ui()

    def _property_changed(self, event) -> None:
        parts = event.contents().split(".")
        if len(parts) >= 3 and parts[1] in ("mode", "output"):
            if parts[2] in (
                "alignStartFrames",
                "useCutInfo",
                "input",
                "size",
                "autoSize",
            ):
                if self._ui is not None:
                    self._update_ui()
        event.reject()

    def _set_selected_input(self, index: int) -> None:
        if self._ui_in_flux or self._selected_combo is None:
            return
        try:
            current = commands.getStringProperty("#RVSwitch.output.input")[0]
            name = self._selected_combo.itemData(index)
            if name and name != current:
                commands.setStringProperty("#RVSwitch.output.input", [name], True)
                commands.redraw()
        except Exception:
            pass

    def _width_changed(self) -> None:
        if self._width_edit is None:
            return
        try:
            val = int(float(self._width_edit.text()))
            prop = commands.getIntProperty("#RVSwitch.output.size")
            commands.setIntProperty("#RVSwitch.output.size", [val, prop[1]], True)
            commands.redraw()
        except Exception:
            pass

    def _height_changed(self) -> None:
        if self._height_edit is None:
            return
        try:
            val = int(float(self._height_edit.text()))
            prop = commands.getIntProperty("#RVSwitch.output.size")
            commands.setIntProperty("#RVSwitch.output.size", [prop[0], val], True)
            commands.redraw()
        except Exception:
            pass

    def _load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None or not mgr._panel_alive():
            event.reject()
            return
        if self._ui is None:
            self._ui = load_ui_file("switch.ui", qtutils.sessionWindow())
            if self._ui is None:
                event.reject()
                return
            self._align_check = self._ui.findChild(QCheckBox, "alignCheckBox")
            self._use_cut_check = self._ui.findChild(QCheckBox, "useCutInfoCheckBox")
            self._auto_size_check = self._ui.findChild(QCheckBox, "autoSizeCheckBox")
            self._selected_combo = self._ui.findChild(QComboBox, "selectedInputCombo")
            self._width_edit = self._ui.findChild(QLineEdit, "outputWidthEdit")
            self._height_edit = self._ui.findChild(QLineEdit, "outputHeightEdit")
            if self._align_check is not None:
                self._align_check.stateChanged.connect(
                    lambda s: self._check_box_slot(s, "#RVSwitch.mode.alignStartFrames")
                )
            if self._use_cut_check is not None:
                self._use_cut_check.stateChanged.connect(
                    lambda s: self._check_box_slot(s, "#RVSwitch.mode.useCutInfo")
                )
            if self._auto_size_check is not None:
                self._auto_size_check.stateChanged.connect(
                    lambda s: self._check_box_slot(s, "#RVSwitch.output.autoSize")
                )
            if self._selected_combo is not None:
                self._selected_combo.currentIndexChanged.connect(self._set_selected_input)
            if self._width_edit is not None:
                self._width_edit.editingFinished.connect(self._width_changed)
            if self._height_edit is not None:
                self._height_edit.editingFinished.connect(self._height_changed)
        if not ensure_editor(mgr, "Switch", self._ui):
            event.reject()
            return
        self._update_ui()
        mgr.useEditor("Switch")
        event.reject()


def createMode():
    return SwitchEditMode()
