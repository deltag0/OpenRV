#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
from rv import rvtypes

try:
    from PySide6.QtWidgets import QComboBox, QLineEdit, QSlider, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtWidgets import QComboBox, QLineEdit, QSlider, QWidget

from sm_edit_support import ensure_editor, load_ui_file, session_manager, set_mode_active, set_modes_active


class LayoutGroupEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._ui: QWidget | None = None
        self.init(
            "LayoutGroup_edit_mode",
            [
                ("session-manager-load-ui", self._load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
            ],
            None,
            None,
            "a",
        )

    def _layout_mode(self) -> str:
        try:
            return commands.getStringProperty("#RVLayoutGroup.layout.mode")[0]
        except Exception:
            return ""

    def _set_layout_mode(self, mode: str) -> None:
        commands.setStringProperty("#RVLayoutGroup.layout.mode", [mode], True)

    def _set_spacing(self, value: float) -> None:
        commands.setFloatProperty("#RVLayoutGroup.layout.spacing", [value], True)

    def _set_grid_rows_columns(self, rows: int, columns: int) -> None:
        commands.setIntProperty("#RVLayoutGroup.layout.gridRows", [rows], True)
        commands.setIntProperty("#RVLayoutGroup.layout.gridColumns", [columns], True)
        self._set_layout_mode("grid")

    def _update_ui(self) -> None:
        if self._ui is None:
            return
        combo = self._ui.findChild(QComboBox, "modeCombo")
        slider = self._ui.findChild(QSlider, "spacingSlider")
        rows_edit = self._ui.findChild(QLineEdit, "gridRowsLineEdit")
        cols_edit = self._ui.findChild(QLineEdit, "gridColumnsLineEdit")
        try:
            mode_map = {
                "packed": 0,
                "packed2": 1,
                "row": 2,
                "column": 3,
                "grid": 4,
                "manual": 5,
            }
            if combo is not None:
                combo.setCurrentIndex(mode_map.get(self._layout_mode(), 6))
            if slider is not None:
                sp = commands.getFloatProperty("#RVLayoutGroup.layout.spacing")[0]
                sp = max(0.5, min(1.0, sp))
                slider.setValue(int((sp * 2.0 - 1.0) * 999.0))
            if rows_edit is not None:
                rows_edit.setText(str(commands.getIntProperty("#RVLayoutGroup.layout.gridRows")[0]))
            if cols_edit is not None:
                cols_edit.setText(
                    str(commands.getIntProperty("#RVLayoutGroup.layout.gridColumns")[0])
                )
        except Exception:
            if combo is not None:
                combo.setCurrentIndex(0)

    def _property_changed(self, event) -> None:
        parts = event.contents().split(".")
        if len(parts) >= 3 and parts[1] == "layout" and self._ui is not None:
            self._update_ui()
            commands.redraw()
        event.reject()

    def _spacing_changed(self, value: int) -> None:
        self._set_spacing(float(value) / 999.0 / 2.0 + 0.5)

    def _rows_changed(self) -> None:
        rows_edit = self._ui.findChild(QLineEdit, "gridRowsLineEdit") if self._ui else None
        if rows_edit is None:
            return
        try:
            self._set_grid_rows_columns(int(rows_edit.text()), 0)
            commands.redraw()
        except Exception:
            pass

    def _cols_changed(self) -> None:
        cols_edit = self._ui.findChild(QLineEdit, "gridColumnsLineEdit") if self._ui else None
        if cols_edit is None:
            return
        try:
            self._set_grid_rows_columns(0, int(cols_edit.text()))
            commands.redraw()
        except Exception:
            pass

    def _mode_changed(self, index: int) -> None:
        modes = ["packed", "packed2", "row", "column", "grid", "manual", "static"]
        if 0 <= index < len(modes):
            self._set_layout_mode(modes[index])
            self._activate_transform_mode(modes[index] == "manual")

    def _activate_ui(self, on: bool) -> None:
        set_modes_active(["Stack_edit_mode", "Composite_edit_mode"], on)

    def _activate_transform_mode(self, on: bool) -> None:
        set_mode_active("transform_manip", on)

    def _load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None or not mgr._panel_alive():
            event.reject()
            return
        if self._ui is None:
            self._ui = load_ui_file("layout.ui", qtutils.sessionWindow())
            if self._ui is None:
                event.reject()
                return
            combo = self._ui.findChild(QComboBox, "modeCombo")
            slider = self._ui.findChild(QSlider, "spacingSlider")
            rows_edit = self._ui.findChild(QLineEdit, "gridRowsLineEdit")
            cols_edit = self._ui.findChild(QLineEdit, "gridColumnsLineEdit")
            if combo is not None:
                combo.currentIndexChanged.connect(self._mode_changed)
            if slider is not None:
                slider.sliderMoved.connect(self._spacing_changed)
            if rows_edit is not None:
                rows_edit.editingFinished.connect(self._rows_changed)
            if cols_edit is not None:
                cols_edit.editingFinished.connect(self._cols_changed)
        if not ensure_editor(mgr, "Layout", self._ui):
            event.reject()
            return
        self._update_ui()
        mgr.useEditor("Layout")
        event.reject()

    def activate(self) -> None:
        self._activate_ui(True)
        self._activate_transform_mode(self._layout_mode() == "manual")

    def deactivate(self) -> None:
        self._activate_ui(False)
        self._activate_transform_mode(False)


def createMode():
    return LayoutGroupEditMode()
