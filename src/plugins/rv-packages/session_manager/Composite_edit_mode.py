#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
from rv import rvtypes

try:
    from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QSlider, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtWidgets import QComboBox, QLabel, QLineEdit, QSlider, QWidget

from sm_edit_support import ensure_editor, load_ui_file, session_manager

_COMPOSITE_OPS = ["over", "add", "dissolve", "difference", "-difference", "replace", "topmost"]


class CompositeEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._ui: QWidget | None = None
        self._combo: QComboBox | None = None
        self._dissolve_edit: QLineEdit | None = None
        self._dissolve_label: QLabel | None = None
        self._dissolve_slider: QSlider | None = None
        self.init(
            "Composite_edit_mode",
            None,
            [
                ("session-manager-load-ui", self._load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
            ],
            None,
            "b",
        )

    def _set_op(self, index: int) -> None:
        if 0 <= index < len(_COMPOSITE_OPS):
            commands.setStringProperty(
                "#RVStack.composite.type", [_COMPOSITE_OPS[index]], True
            )
            self._update_ui()
            commands.redraw()

    def _set_dissolve_amount(self) -> None:
        if self._dissolve_edit is None:
            return
        try:
            amount = float(self._dissolve_edit.text())
            amount = max(0.0, min(1.0, amount))
            if self._dissolve_slider is not None:
                self._dissolve_slider.setValue(int(amount * 100.0))
            commands.setFloatProperty("#RVStack.composite.dissolveAmount", [amount], True)
            commands.redraw()
        except Exception:
            pass

    def _set_dissolve_from_slider(self, value: int) -> None:
        amount = float(value) / 100.0
        if self._dissolve_edit is not None:
            self._dissolve_edit.setText(str(amount))
        commands.setFloatProperty("#RVStack.composite.dissolveAmount", [amount], True)
        commands.redraw()

    def _update_ui(self) -> None:
        if self._ui is None or self._combo is None:
            return
        try:
            current = commands.getStringProperty("#RVStack.composite.type")[0]
            index = _COMPOSITE_OPS.index(current) if current in _COMPOSITE_OPS else 0
            self._combo.setCurrentIndex(index)
            show = current == "dissolve"
            for w in (self._dissolve_edit, self._dissolve_label, self._dissolve_slider):
                if w is not None:
                    w.setVisible(show)
            if show:
                try:
                    amount = commands.getFloatProperty("#RVStack.composite.dissolveAmount")[0]
                    if self._dissolve_edit is not None:
                        self._dissolve_edit.setText(str(amount))
                    if self._dissolve_slider is not None:
                        self._dissolve_slider.setValue(int(amount * 100.0))
                except Exception:
                    if self._dissolve_edit is not None:
                        self._dissolve_edit.setText("0.5")
                    if self._dissolve_slider is not None:
                        self._dissolve_slider.setValue(50)
            self._ui.adjustSize()
            self._ui.updateGeometry()
            self._ui.update()
        except Exception:
            pass

    def _property_changed(self, event) -> None:
        parts = event.contents().split(".")
        if len(parts) >= 3 and parts[1] == "composite":
            if parts[2] in ("type", "dissolveAmount"):
                self._update_ui()
        event.reject()

    def _load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None or not mgr._panel_alive():
            event.reject()
            return
        if self._ui is None:
            self._ui = load_ui_file("composite.ui", qtutils.sessionWindow())
            if self._ui is None:
                event.reject()
                return
            self._combo = self._ui.findChild(QComboBox, "comboBox")
            self._dissolve_edit = self._ui.findChild(QLineEdit, "dissolveLineEdit")
            self._dissolve_label = self._ui.findChild(QLabel, "dissolveLabel")
            self._dissolve_slider = self._ui.findChild(QSlider, "dissolveSlider")
            for w in (self._dissolve_edit, self._dissolve_label, self._dissolve_slider):
                if w is not None:
                    w.setVisible(False)
            if self._combo is not None:
                self._combo.currentIndexChanged.connect(self._set_op)
            if self._dissolve_edit is not None:
                self._dissolve_edit.editingFinished.connect(self._set_dissolve_amount)
            if self._dissolve_slider is not None:
                self._dissolve_slider.valueChanged.connect(self._set_dissolve_from_slider)
        if not ensure_editor(mgr, "Composite Function", self._ui):
            event.reject()
            return
        self._update_ui()
        mgr.useEditor("Composite Function")
        event.reject()


def createMode():
    return CompositeEditMode()
