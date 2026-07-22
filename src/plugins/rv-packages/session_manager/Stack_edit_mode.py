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


class StackEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._ui: QWidget | None = None
        self._ui_in_flux = False
        self.init(
            "Stack_edit_mode",
            None,
            [
                ("session-manager-load-ui", self._load_ui, "Load UI into Session Manager"),
                ("range-changed", self._update_ui_event, "Update UI"),
                ("image-structure-change", self._update_ui_event, "Update UI"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
            ],
            None,
            "z",
        )

    def _check_box_slot(self, state: int, name: str) -> None:
        try:
            v = commands.getIntProperty(name)[0]
            new_v = checkbox_to_int(state)
            if v != new_v:
                commands.setIntProperty(name, [new_v], True)
        except Exception:
            pass

    def _update_ui(self) -> None:
        if self._ui is None or commands.viewNode() is None:
            return
        self._ui_in_flux = True
        try:
            align = self._ui.findChild(QCheckBox, "alignCheckBox")
            strict = self._ui.findChild(QCheckBox, "strictRangesCheckBox")
            use_cut = self._ui.findChild(QCheckBox, "useCutInfoCheckBox")
            retime = self._ui.findChild(QCheckBox, "retimeInputsCheckBox")
            auto_size = self._ui.findChild(QCheckBox, "autoSizeCheckBox")
            interactive = self._ui.findChild(QCheckBox, "interactiveResizeCheckBox")
            audio = self._ui.findChild(QComboBox, "chosenAudioInputCombo")
            fps_edit = self._ui.findChild(QLineEdit, "outputFPSEdit")
            width_edit = self._ui.findChild(QLineEdit, "outputWidthEdit")
            height_edit = self._ui.findChild(QLineEdit, "outputHeightEdit")

            a = commands.getIntProperty("#RVStack.mode.alignStartFrames")[0]
            st = commands.getIntProperty("#RVStack.mode.strictFrameRanges")[0]
            u = commands.getIntProperty("#RVStack.mode.useCutInfo")[0]
            c = commands.getStringProperty("#RVStack.output.chosenAudioInput")[0]
            asize = commands.getIntProperty("#RVStack.output.autoSize")[0]
            size = commands.getIntProperty("#RVStack.output.size")
            fps = commands.getFloatProperty("#RVStack.output.fps")[0]
            isize = commands.getIntProperty("#RVStack.output.interactiveSize")[0]

            if align is not None:
                align.setCheckState(Qt.Checked if a else Qt.Unchecked)
            if strict is not None:
                strict.setCheckState(Qt.Checked if st else Qt.Unchecked)
            if use_cut is not None:
                use_cut.setCheckState(Qt.Checked if u else Qt.Unchecked)
            if auto_size is not None:
                auto_size.setCheckState(Qt.Checked if asize else Qt.Unchecked)
            if interactive is not None:
                interactive.setCheckState(Qt.Checked if isize else Qt.Unchecked)
            if audio is not None:
                audio.clear()
                audio.addItem("All Inputs Mixed", ".all.")
                audio.addItem("First Input Only", ".first.")
                audio.addItem("First Visible Input", ".topmost.")
                chosen = 0
                inputs = commands.nodeConnections(commands.viewNode(), False)[0]
                if c == ".first.":
                    chosen = 1
                elif c == ".topmost.":
                    chosen = 2
                for i, inp in enumerate(inputs):
                    audio.addItem(extra_commands.uiName(inp), inp)
                    if inp == c:
                        chosen = i + 3
                audio.setCurrentIndex(chosen)
            if width_edit is not None:
                width_edit.setEnabled(asize == 0)
                width_edit.setText(str(size[0]))
            if height_edit is not None:
                height_edit.setEnabled(asize == 0)
                height_edit.setText(str(size[1]))
            if fps_edit is not None:
                fps_edit.setText(str(fps))
            if retime is not None:
                prop = "#View.timing.retimeInputs"
                if commands.propertyExists(prop):
                    r = commands.getIntProperty(prop)[0]
                    retime.setCheckState(Qt.Checked if r else Qt.Unchecked)
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
                "strictFrameRanges",
                "useCutInfo",
                "chosenAudioInput",
                "size",
                "autoSize",
                "fps",
                "interactiveSize",
            ):
                if self._ui is not None:
                    self._update_ui()
        event.reject()

    def _set_audio(self, index: int) -> None:
        if self._ui_in_flux:
            return
        audio = self._ui.findChild(QComboBox, "chosenAudioInputCombo") if self._ui else None
        if audio is None:
            return
        try:
            current = commands.getStringProperty("#RVStack.output.chosenAudioInput")[0]
            name = audio.itemData(index)
            if name is None:
                name = ".all."
            if str(name) != current:
                commands.setStringProperty("#RVStack.output.chosenAudioInput", [str(name)], True)
                commands.redraw()
        except Exception:
            pass

    def _fps_changed(self) -> None:
        fps_edit = self._ui.findChild(QLineEdit, "outputFPSEdit") if self._ui else None
        if fps_edit is None:
            return
        try:
            new_fps = float(fps_edit.text())
            commands.setFloatProperty("#RVStack.output.fps", [new_fps], True)
            commands.setFPS(new_fps)
            commands.redraw()
        except Exception:
            pass

    def _width_changed(self) -> None:
        width_edit = self._ui.findChild(QLineEdit, "outputWidthEdit") if self._ui else None
        if width_edit is None:
            return
        try:
            val = int(float(width_edit.text()))
            prop = commands.getIntProperty("#RVStack.output.size")
            commands.setIntProperty("#RVStack.output.size", [val, prop[1]], True)
            commands.redraw()
        except Exception:
            pass

    def _height_changed(self) -> None:
        height_edit = self._ui.findChild(QLineEdit, "outputHeightEdit") if self._ui else None
        if height_edit is None:
            return
        try:
            val = int(float(height_edit.text()))
            prop = commands.getIntProperty("#RVStack.output.size")
            commands.setIntProperty("#RVStack.output.size", [prop[0], val], True)
            commands.redraw()
        except Exception:
            pass

    def _wire_ui(self) -> None:
        if self._ui is None:
            return
        bindings = [
            ("alignCheckBox", "#RVStack.mode.alignStartFrames"),
            ("strictRangesCheckBox", "#RVStack.mode.strictFrameRanges"),
            ("useCutInfoCheckBox", "#RVStack.mode.useCutInfo"),
            ("autoSizeCheckBox", "#RVStack.output.autoSize"),
            ("retimeInputsCheckBox", "#View.timing.retimeInputs"),
            ("interactiveResizeCheckBox", "#RVStack.output.interactiveSize"),
        ]
        for child_name, prop in bindings:
            w = self._ui.findChild(QCheckBox, child_name)
            if w is not None:
                w.stateChanged.connect(lambda s, p=prop: self._check_box_slot(s, p))
        audio = self._ui.findChild(QComboBox, "chosenAudioInputCombo")
        if audio is not None:
            audio.currentIndexChanged.connect(self._set_audio)
        fps_edit = self._ui.findChild(QLineEdit, "outputFPSEdit")
        if fps_edit is not None:
            fps_edit.editingFinished.connect(self._fps_changed)
        width_edit = self._ui.findChild(QLineEdit, "outputWidthEdit")
        if width_edit is not None:
            width_edit.editingFinished.connect(self._width_changed)
        height_edit = self._ui.findChild(QLineEdit, "outputHeightEdit")
        if height_edit is not None:
            height_edit.editingFinished.connect(self._height_changed)

    def _load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None or not mgr._panel_alive():
            event.reject()
            return
        if self._ui is None:
            self._ui = load_ui_file("stack.ui", qtutils.sessionWindow())
            if self._ui is None:
                event.reject()
                return
            self._wire_ui()
        if not ensure_editor(mgr, "Stack", self._ui):
            event.reject()
            return
        self._update_ui()
        mgr.useEditor("Stack")
        event.reject()


def createMode():
    return StackEditMode()
