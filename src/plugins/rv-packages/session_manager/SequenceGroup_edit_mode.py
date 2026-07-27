#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
import rv.rvtypes as rvtypes

from sm_edit_support import checkbox_to_int, load_ui_file, session_manager

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QCheckBox, QLineEdit, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QCheckBox, QLineEdit, QWidget

g_the_mode = None


class SequenceGroupEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._ui = None
        self._auto_edl_checkbox = None
        self._use_cut_info_checkbox = None
        self._retime_checkbox = None
        self._auto_size_checkbox = None
        self._interactive_size_checkbox = None
        self._output_fps_edit = None
        self._output_width_edit = None
        self._output_height_edit = None
        self._disable_updates = False

        self.init(
            "SequenceGroup_edit_mode",
            None,
            [
                ("session-manager-load-ui", self.load_ui, "Load UI into Session Manager"),
                ("range-changed", self.update_ui_event, "Update UI on range change"),
                ("image-structure-change", self.update_ui_event, "Update UI on range change"),
                ("before-session-read", self.before_session_read, "Freeze Updates"),
                ("after-session-read", self.after_session_read, "Resume Updates"),
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            self._menu(),
            None,
        )

    def before_session_read(self, event) -> None:
        self._disable_updates = True
        event.reject()

    def after_session_read(self, event) -> None:
        self._disable_updates = False
        self.update_ui()
        event.reject()

    def update_ui(self) -> None:
        if self._ui is None or self._disable_updates:
            return

        try:
            if not commands.propertyExists("#RVSequence.mode.autoEDL"):
                return
        except Exception:
            return

        try:
            auto_edl = commands.getIntProperty("#RVSequence.mode.autoEDL")[0]
            use_cut = commands.getIntProperty("#RVSequence.mode.useCutInfo")[0]
            retime = commands.getIntProperty("#RVSequenceGroup.timing.retimeInputs")[0]
            fps = commands.getFloatProperty("#RVSequence.output.fps")[0]
            auto_size = commands.getIntProperty("#RVSequence.output.autoSize")[0]
            size = commands.getIntProperty("#RVSequence.output.size")
            interactive_size = commands.getIntProperty("#RVSequence.output.interactiveSize")[0]
        except Exception:
            return

        self._output_width_edit.setEnabled(auto_size == 0 and interactive_size == 0)
        self._output_height_edit.setEnabled(auto_size == 0 and interactive_size == 0)

        self._auto_edl_checkbox.setCheckState(
            Qt.Checked if auto_edl else Qt.Unchecked
        )
        self._use_cut_info_checkbox.setCheckState(
            Qt.Checked if use_cut else Qt.Unchecked
        )
        self._retime_checkbox.setCheckState(Qt.Checked if retime else Qt.Unchecked)
        self._auto_size_checkbox.setCheckState(
            Qt.Checked if auto_size else Qt.Unchecked
        )
        self._output_fps_edit.setText("%g" % fps)
        self._output_width_edit.setText("%d" % size[0])
        self._output_height_edit.setText("%d" % size[1])
        self._interactive_size_checkbox.setCheckState(
            Qt.Checked if interactive_size else Qt.Unchecked
        )

    def update_ui_event(self, event) -> None:
        event.reject()
        self.update_ui()

    def fps_changed(self) -> None:
        try:
            new_fps = float(self._output_fps_edit.text())
            old_fps = commands.getFloatProperty("#RVSequence.output.fps")[0]
            if new_fps != old_fps:
                commands.set("#RVSequence.output.fps", new_fps)
                commands.setFPS(new_fps)
                commands.redraw()
        except Exception:
            pass

    def width_changed(self) -> None:
        try:
            val = float(self._output_width_edit.text())
            prop = commands.getIntProperty("#RVSequence.output.size")
            commands.setIntProperty("#RVSequence.output.size", [int(val), prop[1]])
            commands.redraw()
        except Exception:
            pass

    def height_changed(self) -> None:
        try:
            val = float(self._output_height_edit.text())
            prop = commands.getIntProperty("#RVSequence.output.size")
            commands.setIntProperty("#RVSequence.output.size", [prop[0], int(val)])
            commands.redraw()
        except Exception:
            pass

    def property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) < 3:
            event.reject()
            return

        comp = parts[1]
        name = parts[2]

        if comp in ("mode", "output") and name in (
            "autoEDL",
            "autoSize",
            "useCutInfo",
            "width",
            "fps",
            "height",
            "interactiveSize",
        ):
            self.update_ui()
            commands.redraw()

        event.reject()

    def check_box_slot(self, state: int, name: str) -> None:
        try:
            current = commands.getIntProperty(name)[0]
            value = checkbox_to_int(state)
            if value != current:
                commands.set(name, value)
        except Exception:
            pass

    def activate_ui(self) -> None:
        mgr = session_manager()
        if mgr is None:
            return

        parent = qtutils.sessionWindow()

        if self._ui is None:
            self._ui = load_ui_file("sequence.ui", parent)
            if self._ui is None:
                return

            self._auto_edl_checkbox = self._ui.findChild(QCheckBox, "autoEDLCheckBox")
            self._use_cut_info_checkbox = self._ui.findChild(QCheckBox, "useCutInfoCheckBox")
            self._retime_checkbox = self._ui.findChild(QCheckBox, "retimeInputsCheckBox")
            self._output_fps_edit = self._ui.findChild(QLineEdit, "outputFPSEdit")
            self._output_width_edit = self._ui.findChild(QLineEdit, "outputWidthEdit")
            self._output_height_edit = self._ui.findChild(QLineEdit, "outputHeightEdit")
            self._auto_size_checkbox = self._ui.findChild(QCheckBox, "autoSizeCheckBox")
            self._interactive_size_checkbox = self._ui.findChild(
                QCheckBox, "interactiveResizeCheckBox"
            )

            mgr.addEditor("Sequence", self._ui)

            if self._auto_edl_checkbox is not None:
                self._auto_edl_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVSequence.mode.autoEDL")
                )
            if self._use_cut_info_checkbox is not None:
                self._use_cut_info_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVSequence.mode.useCutInfo")
                )
            if self._auto_size_checkbox is not None:
                self._auto_size_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVSequence.output.autoSize")
                )
            if self._retime_checkbox is not None:
                self._retime_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(
                        s, "#RVSequenceGroup.timing.retimeInputs"
                    )
                )
            if self._interactive_size_checkbox is not None:
                self._interactive_size_checkbox.stateChanged.connect(
                    lambda s: self.check_box_slot(s, "#RVSequence.output.interactiveSize")
                )
            if self._output_fps_edit is not None:
                self._output_fps_edit.editingFinished.connect(self.fps_changed)
            if self._output_width_edit is not None:
                self._output_width_edit.editingFinished.connect(self.width_changed)
            if self._output_height_edit is not None:
                self._output_height_edit.editingFinished.connect(self.height_changed)

        self.update_ui()
        mgr.useEditor("Sequence")

    def load_ui(self, event) -> None:
        self._disable_updates = False
        self.activate_ui()
        event.reject()

    def activate(self) -> None:
        self._disable_updates = False
        self.activate_ui()

    def auto_edl(self, _event) -> None:
        prop = "#RVSequence.mode.autoEDL"
        current = commands.getIntProperty(prop)[0]
        commands.set(prop, 0 if current else 1)

    def use_cut_info(self, _event) -> None:
        prop = "#RVSequence.mode.useCutInfo"
        current = commands.getIntProperty(prop)[0]
        commands.set(prop, 0 if current else 1)

    def state_func(self, name: str):
        def state():
            try:
                value = commands.getIntProperty("#RVSequence.mode.%s" % name)[0]
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
                "Sequence",
                [
                    ("_", None),
                    ("Auto EDL", self.auto_edl, None, self.state_func("autoEDL")),
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
    g_the_mode = SequenceGroupEditMode()
    return g_the_mode
