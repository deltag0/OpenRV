#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
from rv import rvtypes

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QCheckBox, QLineEdit, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QCheckBox, QLineEdit, QWidget

from sm_edit_support import checkbox_to_int, ensure_editor, load_ui_file, session_manager


class SequenceGroupEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._ui: QWidget | None = None
        self._disable_updates = False
        self.init(
            "SequenceGroup_edit_mode",
            None,
            [
                ("session-manager-load-ui", self._load_ui, "Load UI into Session Manager"),
                ("range-changed", self._update_ui_event, "Update UI on range change"),
                ("image-structure-change", self._update_ui_event, "Update UI on range change"),
                ("before-session-read", self._before_session_read, "Freeze Updates"),
                ("after-session-read", self._after_session_read, "Resume Updates"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
            ],
            None,
        )

    def _check_box_slot(self, state: int, name: str) -> None:
        try:
            current = commands.getIntProperty(name)[0]
            value = checkbox_to_int(state)
            if value != current:
                commands.setIntProperty(name, [value], True)
        except Exception:
            pass

    def _update_ui(self) -> None:
        if self._ui is None or self._disable_updates:
            return
        try:
            if not commands.propertyExists("#RVSequence.mode.autoEDL"):
                return
        except Exception:
            return
        try:
            a = commands.getIntProperty("#RVSequence.mode.autoEDL")[0]
            u = commands.getIntProperty("#RVSequence.mode.useCutInfo")[0]
            r = commands.getIntProperty("#RVSequenceGroup.timing.retimeInputs")[0]
            fps = commands.getFloatProperty("#RVSequence.output.fps")[0]
            asize = commands.getIntProperty("#RVSequence.output.autoSize")[0]
            size = commands.getIntProperty("#RVSequence.output.size")
            isize = commands.getIntProperty("#RVSequence.output.interactiveSize")[0]
            widgets = {
                "autoEDLCheckBox": a,
                "useCutInfoCheckBox": u,
                "retimeInputsCheckBox": r,
                "autoSizeCheckBox": asize,
                "interactiveResizeCheckBox": isize,
            }
            for name, val in widgets.items():
                w = self._ui.findChild(QCheckBox, name)
                if w is not None:
                    w.setCheckState(Qt.Checked if val else Qt.Unchecked)
            width = self._ui.findChild(QLineEdit, "outputWidthEdit")
            height = self._ui.findChild(QLineEdit, "outputHeightEdit")
            fps_edit = self._ui.findChild(QLineEdit, "outputFPSEdit")
            if width is not None:
                width.setEnabled(asize == 0 and isize == 0)
                width.setText(str(size[0]))
            if height is not None:
                height.setEnabled(asize == 0 and isize == 0)
                height.setText(str(size[1]))
            if fps_edit is not None:
                fps_edit.setText(str(fps))
        except Exception:
            pass

    def _update_ui_event(self, event) -> None:
        event.reject()
        self._update_ui()

    def _before_session_read(self, event) -> None:
        self._disable_updates = True
        event.reject()

    def _after_session_read(self, event) -> None:
        self._disable_updates = False
        self._update_ui()
        event.reject()

    def _property_changed(self, event) -> None:
        parts = event.contents().split(".")
        if len(parts) >= 3 and parts[1] in ("mode", "output"):
            if parts[2] in (
                "autoEDL",
                "autoSize",
                "useCutInfo",
                "width",
                "fps",
                "height",
                "interactiveSize",
            ):
                self._update_ui()
                commands.redraw()
        event.reject()

    def _fps_changed(self) -> None:
        fps_edit = self._ui.findChild(QLineEdit, "outputFPSEdit") if self._ui else None
        if fps_edit is None:
            return
        try:
            new_fps = float(fps_edit.text())
            old_fps = commands.getFloatProperty("#RVSequence.output.fps")[0]
            if new_fps != old_fps:
                commands.setFloatProperty("#RVSequence.output.fps", [new_fps], True)
                commands.setFPS(new_fps)
                commands.redraw()
        except Exception:
            pass

    def _width_changed(self) -> None:
        width = self._ui.findChild(QLineEdit, "outputWidthEdit") if self._ui else None
        if width is None:
            return
        try:
            val = int(float(width.text()))
            prop = commands.getIntProperty("#RVSequence.output.size")
            commands.setIntProperty("#RVSequence.output.size", [val, prop[1]], True)
            commands.redraw()
        except Exception:
            pass

    def _height_changed(self) -> None:
        height = self._ui.findChild(QLineEdit, "outputHeightEdit") if self._ui else None
        if height is None:
            return
        try:
            val = int(float(height.text()))
            prop = commands.getIntProperty("#RVSequence.output.size")
            commands.setIntProperty("#RVSequence.output.size", [prop[0], val], True)
            commands.redraw()
        except Exception:
            pass

    def _wire_ui(self) -> None:
        if self._ui is None:
            return
        for child, prop in (
            ("autoEDLCheckBox", "#RVSequence.mode.autoEDL"),
            ("useCutInfoCheckBox", "#RVSequence.mode.useCutInfo"),
            ("autoSizeCheckBox", "#RVSequence.output.autoSize"),
            ("retimeInputsCheckBox", "#RVSequenceGroup.timing.retimeInputs"),
            ("interactiveResizeCheckBox", "#RVSequence.output.interactiveSize"),
        ):
            w = self._ui.findChild(QCheckBox, child)
            if w is not None:
                w.stateChanged.connect(lambda s, p=prop: self._check_box_slot(s, p))
        fps = self._ui.findChild(QLineEdit, "outputFPSEdit")
        if fps is not None:
            fps.editingFinished.connect(self._fps_changed)
        width = self._ui.findChild(QLineEdit, "outputWidthEdit")
        if width is not None:
            width.editingFinished.connect(self._width_changed)
        height = self._ui.findChild(QLineEdit, "outputHeightEdit")
        if height is not None:
            height.editingFinished.connect(self._height_changed)

    def _activate_ui(self) -> None:
        mgr = session_manager()
        if mgr is None or not mgr._panel_alive():
            return
        if self._ui is None:
            self._ui = load_ui_file("sequence.ui", qtutils.sessionWindow())
            if self._ui is None:
                return
            self._wire_ui()
        if not ensure_editor(mgr, "Sequence", self._ui):
            return
        self._update_ui()
        mgr.useEditor("Sequence")

    def _load_ui(self, event) -> None:
        self._disable_updates = False
        self._activate_ui()
        event.reject()

    def activate(self) -> None:
        self._disable_updates = False
        self._activate_ui()


def createMode():
    return SequenceGroupEditMode()
