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


class StackEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._ui = None
        self._align_checkbox = None
        self._strict_ranges_checkbox = None
        self._use_cut_info_checkbox = None
        self._retime_checkbox = None
        self._auto_size_checkbox = None
        self._interactive_size_checkbox = None
        self._chosen_audio_input_combo = None
        self._output_fps_edit = None
        self._output_width_edit = None
        self._output_height_edit = None
        self._ui_in_flux = False

        self.init(
            "Stack_edit_mode",
            None,
            [
                ("session-manager-load-ui", self.load_ui, "Load UI into Session Manager"),
                ("range-changed", self.update_ui_event, "Update UI"),
                ("image-structure-change", self.update_ui_event, "Update UI"),
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            None,
            "z",
        )

    def update_ui(self) -> None:
        vnode = commands.viewNode()
        if self._ui is None or vnode is None:
            return

        self._ui_in_flux = True

        try:
            align = commands.getIntProperty("#RVStack.mode.alignStartFrames")[0]
            strict = commands.getIntProperty("#RVStack.mode.strictFrameRanges")[0]
            use_cut = commands.getIntProperty("#RVStack.mode.useCutInfo")[0]
            chosen = commands.getStringProperty("#RVStack.output.chosenAudioInput")[0]
            auto_size = commands.getIntProperty("#RVStack.output.autoSize")[0]
            size = commands.getIntProperty("#RVStack.output.size")
            fps = commands.getFloatProperty("#RVStack.output.fps")[0]
            interactive_size = commands.getIntProperty("#RVStack.output.interactiveSize")[0]

            self._align_checkbox.setCheckState(Qt.Checked if align else Qt.Unchecked)
            self._strict_ranges_checkbox.setCheckState(
                Qt.Checked if strict else Qt.Unchecked
            )
            self._use_cut_info_checkbox.setCheckState(
                Qt.Checked if use_cut else Qt.Unchecked
            )
            self._auto_size_checkbox.setCheckState(
                Qt.Checked if auto_size else Qt.Unchecked
            )
            self._interactive_size_checkbox.setCheckState(
                Qt.Checked if interactive_size else Qt.Unchecked
            )

            self._chosen_audio_input_combo.clear()
            self._chosen_audio_input_combo.addItem("All Inputs Mixed", ".all.")
            self._chosen_audio_input_combo.addItem("First Input Only", ".first.")
            self._chosen_audio_input_combo.addItem("First Visible Input", ".topmost.")

            chosen_index = 0
            inputs = commands.nodeConnections(vnode, False)[0]
            if chosen == ".first.":
                chosen_index = 1
            elif chosen == ".topmost.":
                chosen_index = 2

            for i, node in enumerate(inputs):
                self._chosen_audio_input_combo.addItem(extra_commands.uiName(node), node)
                if node == chosen:
                    chosen_index = i + 3

            self._chosen_audio_input_combo.setCurrentIndex(chosen_index)

            self._output_width_edit.setEnabled(auto_size == 0)
            self._output_height_edit.setEnabled(auto_size == 0)
            self._output_fps_edit.setText("%g" % fps)
            self._output_width_edit.setText("%d" % size[0])
            self._output_height_edit.setText("%d" % size[1])

            retime_prop = "#View.timing.retimeInputs"
            if commands.propertyExists(retime_prop):
                retime = commands.getIntProperty(retime_prop)[0]
                self._retime_checkbox.setCheckState(
                    Qt.Checked if retime else Qt.Unchecked
                )
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
            "strictFrameRanges",
            "useCutInfo",
            "chosenAudioInput",
            "size",
            "autoSize",
            "fps",
            "interactiveSize",
        ):
            if self._ui is not None:
                self.update_ui()

        event.reject()

    def check_box_slot(self, state: int, name: str) -> None:
        try:
            current = commands.getIntProperty(name)[0]
            new_value = checkbox_to_int(state)
            if current != new_value:
                commands.set(name, new_value)
        except Exception:
            pass

    def set_chosen_audio_input(self, index: int) -> None:
        if self._ui_in_flux or self._chosen_audio_input_combo is None:
            return

        try:
            current_name = commands.getStringProperty("#RVStack.output.chosenAudioInput")[0]
        except Exception:
            current_name = ".all."

        name = ".all."
        if 0 <= index < self._chosen_audio_input_combo.count():
            data = self._chosen_audio_input_combo.itemData(index, Qt.UserRole)
            if data is not None:
                name = str(data)

        if name != current_name:
            commands.set("#RVStack.output.chosenAudioInput", name)
            commands.redraw()

    def fps_changed(self) -> None:
        try:
            new_fps = float(self._output_fps_edit.text())
            commands.set("#RVStack.output.fps", new_fps)
            commands.setFPS(new_fps)
        except Exception:
            pass
        commands.redraw()

    def width_changed(self) -> None:
        try:
            val = float(self._output_width_edit.text())
            prop = commands.getIntProperty("#RVStack.output.size")
            commands.setIntProperty("#RVStack.output.size", [int(val), prop[1]])
            commands.redraw()
        except Exception:
            pass

    def height_changed(self) -> None:
        try:
            val = float(self._output_height_edit.text())
            prop = commands.getIntProperty("#RVStack.output.size")
            commands.setIntProperty("#RVStack.output.size", [prop[0], int(val)])
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
            self._ui = load_ui_file("stack.ui", parent)
            if self._ui is None:
                event.reject()
                return

            self._align_checkbox = self._ui.findChild(QCheckBox, "alignCheckBox")
            self._strict_ranges_checkbox = self._ui.findChild(
                QCheckBox, "strictRangesCheckBox"
            )
            self._use_cut_info_checkbox = self._ui.findChild(QCheckBox, "useCutInfoCheckBox")
            self._retime_checkbox = self._ui.findChild(QCheckBox, "retimeInputsCheckBox")
            self._auto_size_checkbox = self._ui.findChild(QCheckBox, "autoSizeCheckBox")
            self._chosen_audio_input_combo = self._ui.findChild(
                QComboBox, "chosenAudioInputCombo"
            )
            self._output_fps_edit = self._ui.findChild(QLineEdit, "outputFPSEdit")
            self._output_width_edit = self._ui.findChild(QLineEdit, "outputWidthEdit")
            self._output_height_edit = self._ui.findChild(QLineEdit, "outputHeightEdit")
            self._interactive_size_checkbox = self._ui.findChild(
                QCheckBox, "interactiveResizeCheckBox"
            )

            mgr.addEditor("Stack", self._ui)

            if self._align_checkbox is not None:
                self._align_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVStack.mode.alignStartFrames")
                )
            if self._strict_ranges_checkbox is not None:
                self._strict_ranges_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVStack.mode.strictFrameRanges")
                )
            if self._use_cut_info_checkbox is not None:
                self._use_cut_info_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVStack.mode.useCutInfo")
                )
            if self._auto_size_checkbox is not None:
                self._auto_size_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVStack.output.autoSize")
                )
            if self._retime_checkbox is not None:
                self._retime_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#View.timing.retimeInputs")
                )
            if self._interactive_size_checkbox is not None:
                self._interactive_size_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVStack.output.interactiveSize")
                )
            if self._chosen_audio_input_combo is not None:
                self._chosen_audio_input_combo.currentIndexChanged.connect(
                    self.set_chosen_audio_input
                )
            if self._output_fps_edit is not None:
                self._output_fps_edit.editingFinished.connect(self.fps_changed)
            if self._output_width_edit is not None:
                self._output_width_edit.editingFinished.connect(self.width_changed)
            if self._output_height_edit is not None:
                self._output_height_edit.editingFinished.connect(self.height_changed)

        self.update_ui()
        mgr.useEditor("Stack")
        event.reject()

    def align_start_frames(self, _event) -> None:
        prop = "#RVStack.mode.alignStartFrames"
        current = commands.getIntProperty(prop)[0]
        commands.set(prop, 0 if current else 1)

    def strict_frame_ranges(self, _event) -> None:
        prop = "#RVStack.mode.strictFrameRanges"
        current = commands.getIntProperty(prop)[0]
        commands.set(prop, 0 if current else 1)

    def use_cut_info(self, _event) -> None:
        prop = "#RVStack.mode.useCutInfo"
        current = commands.getIntProperty(prop)[0]
        commands.set(prop, 0 if current else 1)

    def state_func(self, name: str):
        def state():
            try:
                value = commands.getIntProperty("#RVStack.mode.%s" % name)[0]
                return (
                    commands.CheckedMenuState
                    if value
                    else commands.UncheckedMenuState
                )
            except Exception:
                return commands.UncheckedMenuState

        return state

    def retime_state(self):
        try:
            value = commands.getIntProperty("#View.timing.retimeInputs")[0]
            return (
                commands.CheckedMenuState
                if value
                else commands.UncheckedMenuState
            )
        except Exception:
            return commands.UncheckedMenuState

    def auto_retime_inputs(self, _event) -> None:
        prop = "#View.timing.retimeInputs"
        current = commands.getIntProperty(prop)[0]
        commands.set(prop, 0 if current else 1)


def createMode():
    global g_the_mode
    g_the_mode = StackEditMode()
    return g_the_mode
