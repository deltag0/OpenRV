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
    from PySide6.QtWidgets import QComboBox, QLineEdit, QSlider, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QComboBox, QLineEdit, QSlider, QWidget

g_the_mode = None


class LayoutGroupEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._ui = None
        self._mode_combo = None
        self._spacing_slider = None
        self._grid_rows_line_edit = None
        self._grid_columns_line_edit = None

        self.init(
            "LayoutGroup_edit_mode",
            [
                ("session-manager-load-ui", self.load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            None,
            self._menu(),
            "a",
        )

        self.activate_transform_mode(self.layout_mode() == "manual")

    def layout_mode(self) -> str:
        try:
            return commands.getStringProperty("#RVLayoutGroup.layout.mode")[0]
        except Exception:
            return ""

    def set_layout_mode(self, mode: str) -> None:
        commands.setStringProperty("#RVLayoutGroup.layout.mode", [mode], True)

    def set_spacing(self, value: float) -> None:
        commands.setFloatProperty("#RVLayoutGroup.layout.spacing", [value], True)

    def set_grid_rows_columns(self, rows: int, columns: int) -> None:
        prop = "#RVLayoutGroup.layout."
        commands.setIntProperty(prop + "gridRows", [rows], True)
        commands.setIntProperty(prop + "gridColumns", [columns], True)
        self.set_layout_mode("grid")

    def update_ui(self) -> None:
        if self._ui is None:
            return

        try:
            mode = self.layout_mode()
            index_map = {
                "packed": 0,
                "packed2": 1,
                "row": 2,
                "column": 3,
                "grid": 4,
                "manual": 5,
                "static": 6,
            }
            if self._mode_combo is not None:
                self._mode_combo.setCurrentIndex(index_map.get(mode, 6))

            spacing = commands.getFloatProperty("#RVLayoutGroup.layout.spacing")[0]
            clamped = max(0.5, min(1.0, spacing))
            if self._spacing_slider is not None:
                self._spacing_slider.setValue(int((clamped * 2.0 - 1.0) * 999.0))

            rows = commands.getIntProperty("#RVLayoutGroup.layout.gridRows")[0]
            columns = commands.getIntProperty("#RVLayoutGroup.layout.gridColumns")[0]
            if self._grid_rows_line_edit is not None:
                self._grid_rows_line_edit.setText("%d" % rows)
            if self._grid_columns_line_edit is not None:
                self._grid_columns_line_edit.setText("%d" % columns)
        except Exception:
            if self._mode_combo is not None:
                self._mode_combo.setCurrentIndex(0)

    def property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) >= 3 and parts[1] == "layout":
            if parts[2] in ("mode", "spacing", "gridRows", "gridColumns"):
                if self._ui is not None:
                    self.update_ui()
                if parts[2] == "mode":
                    self.activate_transform_mode(self.layout_mode() == "manual")
                    if self.layout_mode() == "manual":
                        try:
                            import transform_manip as tm

                            manip = tm.theMode()
                            if manip is not None:
                                manip.find_editing_nodes()
                        except Exception:
                            pass
                commands.redraw()
        event.reject()

    def spacing_slider_changed_slot(self, value: int) -> None:
        self.set_spacing(float(value) / 999.0 / 2.0 + 0.5)

    def grid_rows_changed_slot(self) -> None:
        try:
            new_rows = int(self._grid_rows_line_edit.text())
            self.set_grid_rows_columns(new_rows, 0)
            commands.redraw()
        except Exception:
            pass

    def grid_columns_changed_slot(self) -> None:
        try:
            new_columns = int(self._grid_columns_line_edit.text())
            self.set_grid_rows_columns(0, new_columns)
            commands.redraw()
        except Exception:
            pass

    def mode_combo_changed_slot(self, index: int) -> None:
        handlers = [
            self.layout_packed,
            self.layout_packed2,
            self.layout_in_row,
            self.layout_in_column,
            self.layout_in_grid,
            self.layout_manually,
            self.layout_static,
        ]
        if 0 <= index < len(handlers):
            handlers[index]()
        else:
            self.layout_static()

    def load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None:
            event.reject()
            return

        parent = qtutils.sessionWindow()

        if self._ui is None:
            self._ui = load_ui_file("layout.ui", parent)
            if self._ui is None:
                event.reject()
                return

            self._mode_combo = self._ui.findChild(QComboBox, "modeCombo")
            self._spacing_slider = self._ui.findChild(QSlider, "spacingSlider")
            self._grid_rows_line_edit = self._ui.findChild(QLineEdit, "gridRowsLineEdit")
            self._grid_columns_line_edit = self._ui.findChild(
                QLineEdit, "gridColumnsLineEdit"
            )

            mgr.addEditor("Layout", self._ui)

            if self._mode_combo is not None:
                self._mode_combo.currentIndexChanged.connect(self.mode_combo_changed_slot)
            if self._spacing_slider is not None:
                self._spacing_slider.sliderMoved.connect(self.spacing_slider_changed_slot)
            if self._grid_rows_line_edit is not None:
                self._grid_rows_line_edit.editingFinished.connect(self.grid_rows_changed_slot)
            if self._grid_columns_line_edit is not None:
                self._grid_columns_line_edit.editingFinished.connect(
                    self.grid_columns_changed_slot
                )

        self.update_ui()
        mgr.useEditor("Layout")
        event.reject()

    def layout_in_row(self) -> None:
        self.set_layout_mode("row")
        self.activate_transform_mode(False)

    def layout_in_column(self) -> None:
        self.set_layout_mode("column")
        self.activate_transform_mode(False)

    def layout_packed(self) -> None:
        self.set_layout_mode("packed")
        self.activate_transform_mode(False)

    def layout_in_grid(self) -> None:
        self.set_layout_mode("grid")
        self.activate_transform_mode(False)

    def layout_packed2(self) -> None:
        self.set_layout_mode("packed2")
        self.activate_transform_mode(False)

    def layout_manually(self) -> None:
        self.set_layout_mode("manual")
        self.activate_transform_mode(True)

    def layout_static(self) -> None:
        self.set_layout_mode("static")
        self.activate_transform_mode(False)

    def activate_transform_mode(self, on: bool) -> None:
        set_modes_active(["transform_manip"], on)

    def _activate_ui(self, on: bool) -> None:
        set_modes_active(["Stack_edit_mode", "Composite_edit_mode"], on)

    def deactivate(self) -> None:
        self._activate_ui(False)
        self.activate_transform_mode(False)

    def activate(self) -> None:
        self._activate_ui(True)
        self.activate_transform_mode(self.layout_mode() == "manual")

    def is_layout_mode(self, name: str):
        def state():
            return (
                commands.CheckedMenuState
                if self.layout_mode() == name
                else commands.UncheckedMenuState
            )

        return state

    def _menu(self):
        return [
            (
                "Layout",
                [
                    ("Layout Method", None, None, None),
                    ("    Packed", lambda e: self.layout_packed(), None, self.is_layout_mode("packed")),
                    (
                        "    Packed With Fluid Layout",
                        lambda e: self.layout_packed2(),
                        None,
                        self.is_layout_mode("packed2"),
                    ),
                    ("    Row", lambda e: self.layout_in_row(), None, self.is_layout_mode("row")),
                    (
                        "    Column",
                        lambda e: self.layout_in_column(),
                        None,
                        self.is_layout_mode("column"),
                    ),
                    ("    Grid", lambda e: self.layout_in_grid(), None, self.is_layout_mode("grid")),
                    (
                        "    Manual",
                        lambda e: self.layout_manually(),
                        None,
                        self.is_layout_mode("manual"),
                    ),
                    (
                        "    Static",
                        lambda e: self.layout_static(),
                        None,
                        self.is_layout_mode("static"),
                    ),
                ],
            )
        ]


def createMode():
    global g_the_mode
    g_the_mode = LayoutGroupEditMode()
    return g_the_mode
