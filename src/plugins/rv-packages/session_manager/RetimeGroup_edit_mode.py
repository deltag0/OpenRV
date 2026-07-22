#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
from rv import rvtypes

try:
    from PySide6.QtWidgets import QLineEdit, QPushButton, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtWidgets import QLineEdit, QPushButton, QWidget

from sm_edit_support import ensure_editor, load_ui_file, session_manager


class RetimeGroupEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._ui: QWidget | None = None
        self.init(
            "RetimeGroup_edit_mode",
            None,
            [
                ("session-manager-load-ui", self._load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
            ],
            None,
        )

    def reset(self) -> None:
        commands.setFloatProperty("#RVRetime.visual.scale", [1.0], True)
        commands.setFloatProperty("#RVRetime.visual.offset", [0.0], True)
        commands.setFloatProperty("#RVRetime.audio.scale", [1.0], True)
        commands.setFloatProperty("#RVRetime.audio.offset", [0.0], True)
        commands.redraw()

    def reverse(self) -> None:
        try:
            length = commands.frameEnd() - commands.frameStart()
            scl = commands.getFloatProperty("#RVRetime.visual.scale")[0]
            if scl < 0:
                self.reset()
            else:
                commands.setFloatProperty("#RVRetime.visual.scale", [-1.0], True)
                commands.setFloatProperty("#RVRetime.visual.offset", [float(-length)], True)
                commands.setFloatProperty("#RVRetime.audio.scale", [1.0], True)
                commands.setFloatProperty("#RVRetime.audio.offset", [0.0], True)
            commands.redraw()
        except Exception:
            pass

    def _update_ui(self) -> None:
        if self._ui is None:
            return
        try:
            mapping = (
                ("fpsEdit", "#RVRetime.output.fps", float),
                ("vscaleEdit", "#RVRetime.visual.scale", float),
                ("ascaleEdit", "#RVRetime.audio.scale", float),
                ("voffsetEdit", "#RVRetime.visual.offset", float),
                ("aoffsetEdit", "#RVRetime.audio.offset", float),
            )
            for child, prop, typ in mapping:
                edit = self._ui.findChild(QLineEdit, child)
                if edit is not None:
                    val = typ(commands.getFloatProperty(prop)[0])
                    edit.setText(str(val))
        except Exception:
            pass

    def _edit_slot(self, line_edit: QLineEdit, prop_suffix: str) -> None:
        try:
            val = float(line_edit.text())
            commands.setFloatProperty("#RVRetime" + prop_suffix, [val], True)
            if prop_suffix == ".output.fps":
                commands.setFPS(val)
            commands.redraw()
        except Exception:
            pass

    def _property_changed(self, event) -> None:
        parts = event.contents().split(".")
        if parts and commands.nodeType(parts[0]) == "RVRetime":
            self._update_ui()
        event.reject()

    def _load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None or not mgr._panel_alive():
            event.reject()
            return
        if self._ui is None:
            self._ui = load_ui_file("retime.ui", qtutils.sessionWindow())
            if self._ui is None:
                event.reject()
                return
            reset_btn = self._ui.findChild(QPushButton, "resetButton")
            reverse_btn = self._ui.findChild(QPushButton, "reverseButton")
            if reset_btn is not None:
                reset_btn.clicked.connect(lambda: self.reset())
            if reverse_btn is not None:
                reverse_btn.clicked.connect(lambda: self.reverse())
            for child, suffix in (
                ("fpsEdit", ".output.fps"),
                ("ascaleEdit", ".audio.scale"),
                ("vscaleEdit", ".visual.scale"),
                ("aoffsetEdit", ".audio.offset"),
                ("voffsetEdit", ".visual.offset"),
            ):
                edit = self._ui.findChild(QLineEdit, child)
                if edit is not None:
                    edit.editingFinished.connect(
                        lambda e=edit, s=suffix: self._edit_slot(e, s)
                    )
        if not ensure_editor(mgr, "Retime", self._ui):
            event.reject()
            return
        self._update_ui()
        mgr.useEditor("Retime")
        event.reject()


def createMode():
    return RetimeGroupEditMode()
