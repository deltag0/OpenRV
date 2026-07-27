#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.extra_commands as extra_commands
import rv.qtutils as qtutils
import rv.rvtypes as rvtypes

from sm_edit_support import checkbox_to_int, load_ui_file, session_manager

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QCheckBox, QComboBox, QLineEdit, QWidget

g_the_mode = None


class SwitchEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._ui = None
        self._align_checkbox = None
        self._use_cut_info_checkbox = None
        self._auto_size_checkbox = None
        self._selected_input_combo = None
        self._output_width_edit = None
        self._output_height_edit = None
        self._ui_in_flux = False

        self.init(
            "Switch_edit_mode",
            None,
            [
                ("session-manager-load-ui", self.load_ui, "Load UI into Session Manager"),
                ("range-changed", self.update_ui_event, "Update UI"),
                ("image-structure-change", self.update_ui_event, "Update UI"),
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            self._menu(),
            "z0",
        )

    def update_ui(self) -> None:
        if self._ui is None or commands.viewNode() is None:
            return

        self._ui_in_flux = True

        try:
            align = commands.getIntProperty("#RVSwitch.mode.alignStartFrames")[0]
            use_cut = commands.getIntProperty("#RVSwitch.mode.useCutInfo")[0]
            current = commands.getStringProperty("#RVSwitch.output.input")[0]
            auto_size = commands.getIntProperty("#RVSwitch.output.autoSize")[0]
            size = commands.getIntProperty("#RVSwitch.output.size")

            self._align_checkbox.setCheckState(Qt.Checked if align else Qt.Unchecked)
            self._use_cut_info_checkbox.setCheckState(
                Qt.Checked if use_cut else Qt.Unchecked
            )
            self._auto_size_checkbox.setCheckState(
                Qt.Checked if auto_size else Qt.Unchecked
            )

            self._selected_input_combo.clear()
            selected_index = 0
            inputs = commands.nodeConnections(commands.viewNode(), False)[0]

            for i, node in enumerate(inputs):
                self._selected_input_combo.addItem(extra_commands.uiName(node), node)
                if node == current:
                    selected_index = i

            self._selected_input_combo.setCurrentIndex(selected_index)

            self._output_width_edit.setEnabled(auto_size == 0)
            self._output_height_edit.setEnabled(auto_size == 0)
            self._output_width_edit.setText("%d" % size[0])
            self._output_height_edit.setText("%d" % size[1])
        except Exception:
            pass

        commands.redraw()
        self._ui_in_flux = False

    def update_ui_event(self, event) -> None:
        event.reject()
        self.update_ui()

    def property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) < 3:
            event.reject()
            return

        comp = parts[1]
        name = parts[2]

        if comp in ("mode", "output") and name in (
            "alignStartFrames",
            "useCutInfo",
            "input",
            "size",
            "autoSize",
        ):
            if self._ui is not None:
                self.update_ui()

        event.reject()

    def check_box_slot(self, state: int, name: str) -> None:
        commands.set(name, checkbox_to_int(state))

    def set_selected_input(self, index: int) -> None:
        if self._ui_in_flux or self._selected_input_combo is None:
            return

        try:
            current_name = commands.getStringProperty("#RVSwitch.output.input")[0]
        except Exception:
            current_name = ""

        name = current_name
        if 0 <= index < self._selected_input_combo.count():
            data = self._selected_input_combo.itemData(index, Qt.UserRole)
            if data is not None:
                name = str(data)

        if name != current_name:
            commands.set("#RVSwitch.output.input", name)
            commands.redraw()

    def width_changed(self) -> None:
        try:
            val = float(self._output_width_edit.text())
            prop = commands.getIntProperty("#RVSwitch.output.size")
            commands.setIntProperty("#RVSwitch.output.size", [int(val), prop[1]])
            commands.redraw()
        except Exception:
            pass

    def height_changed(self) -> None:
        try:
            val = float(self._output_height_edit.text())
            prop = commands.getIntProperty("#RVSwitch.output.size")
            commands.setIntProperty("#RVSwitch.output.size", [prop[0], int(val)])
            commands.redraw()
        except Exception:
            pass

    def load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None:
            event.reject()
            return

        parent = qtutils.sessionWindow()

        if self._ui is None:
            self._ui = load_ui_file("switch.ui", parent)
            if self._ui is None:
                event.reject()
                return

            self._align_checkbox = self._ui.findChild(QCheckBox, "alignCheckBox")
            self._use_cut_info_checkbox = self._ui.findChild(QCheckBox, "useCutInfoCheckBox")
            self._auto_size_checkbox = self._ui.findChild(QCheckBox, "autoSizeCheckBox")
            self._selected_input_combo = self._ui.findChild(QComboBox, "selectedInputCombo")
            self._output_width_edit = self._ui.findChild(QLineEdit, "outputWidthEdit")
            self._output_height_edit = self._ui.findChild(QLineEdit, "outputHeightEdit")

            mgr.addEditor("Switch", self._ui)

            if self._align_checkbox is not None:
                self._align_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVSwitch.mode.alignStartFrames")
                )
            if self._use_cut_info_checkbox is not None:
                self._use_cut_info_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVSwitch.mode.useCutInfo")
                )
            if self._auto_size_checkbox is not None:
                self._auto_size_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVSwitch.output.autoSize")
                )
            if self._selected_input_combo is not None:
                self._selected_input_combo.currentIndexChanged.connect(self.set_selected_input)
            if self._output_width_edit is not None:
                self._output_width_edit.editingFinished.connect(self.width_changed)
            if self._output_height_edit is not None:
                self._output_height_edit.editingFinished.connect(self.height_changed)

        self.update_ui()
        mgr.useEditor("Switch")
        event.reject()

    def align_start_frames(self, _event) -> None:
        prop = "#RVSwitch.mode.alignStartFrames"
        current = commands.getIntProperty(prop)[0]
        commands.set(prop, 0 if current else 1)

    def use_cut_info(self, _event) -> None:
        prop = "#RVSwitch.mode.useCutInfo"
        current = commands.getIntProperty(prop)[0]
        commands.set(prop, 0 if current else 1)

    def state_func(self, name: str):
        def state():
            try:
                value = commands.getIntProperty("#RVSwitch.mode.%s" % name)[0]
                return (
                    commands.CheckedMenuState
                    if value
                    else commands.UncheckedMenuState
                )
            except Exception:
                return commands.UncheckedMenuState

        return state

    def _menu(self):
        return [
            (
                "Switch",
                [
                    (
                        "Align Start Frames",
                        self.align_start_frames,
                        None,
                        self.state_func("alignStartFrames"),
                    ),
                    (
                        "Use Source Cut Info",
                        self.use_cut_info,
                        None,
                        self.state_func("useCutInfo"),
                    ),
                ],
            )
        ]


def createMode():
    global g_the_mode
    g_the_mode = SwitchEditMode()
    return g_the_mode
