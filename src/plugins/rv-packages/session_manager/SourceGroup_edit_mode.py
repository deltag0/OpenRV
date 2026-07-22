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
    from PySide6.QtWidgets import QCheckBox, QPushButton, QSpinBox, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QCheckBox, QPushButton, QSpinBox, QWidget

from sm_edit_support import INT_MAX, ensure_editor, load_ui_file, restore_edit_tab, session_manager


class SourceGroupEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._locked = False
        self._ui: QWidget | None = None
        self._cut_in_edit: QSpinBox | None = None
        self._cut_out_edit: QSpinBox | None = None
        self._sync_check_box: QCheckBox | None = None
        self._reset_button: QPushButton | None = None

        self.init(
            "SourceGroup_edit_mode",
            None,
            [
                ("new-in-point", self._new_in_point, "Update In Point"),
                ("new-out-point", self._new_out_point, "Update Out Point"),
                ("session-manager-load-ui", self._load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
            ],
            None,
        )

    def _sync_gui_in_out(self) -> bool:
        prop = "#RVFileSource.cut.syncGui"
        if commands.propertyExists(prop):
            return commands.getIntProperty(prop)[0] != 0
        return True

    def reset(self) -> None:
        self._locked = True
        try:
            if self._sync_gui_in_out():
                commands.setInPoint(commands.frameStart())
                commands.setOutPoint(commands.frameEnd())
            commands.setIntProperty("#RVFileSource.cut.in", [-INT_MAX], True)
            commands.setIntProperty("#RVFileSource.cut.out", [INT_MAX], True)
        except Exception:
            pass
        self._locked = False
        self._update_ui()
        commands.redraw()

    def _update_ui(self) -> None:
        if self._ui is None or self._cut_in_edit is None or self._cut_out_edit is None:
            return
        self._locked = True
        try:
            cut_in = commands.getIntProperty("#RVFileSource.cut.in")[0]
            cut_out = commands.getIntProperty("#RVFileSource.cut.out")[0]
            self._cut_in_edit.setValue(cut_in)
            self._cut_out_edit.setValue(cut_out if cut_out != INT_MAX else -INT_MAX)
            if self._sync_check_box is not None:
                self._sync_check_box.setCheckState(
                    Qt.Checked if self._sync_gui_in_out() else Qt.Unchecked
                )
        except Exception:
            pass
        self._locked = False

    def _reset_slot(self, _checked: bool = False) -> None:
        self.reset()

    def _sync_slot(self, checked: bool) -> None:
        if self._locked:
            return
        prop = "#RVFileSource.cut.syncGui"
        commands.setIntProperty(prop, [1 if checked else 0], True)
        if checked:
            self._update_from_props()
        self._update_ui()

    def _changed_slot(self, prop: str, value: int) -> None:
        if self._locked or value == -INT_MAX:
            return
        if value < commands.frameStart() or value > commands.frameEnd():
            return
        if prop == "in" and value > commands.outPoint():
            return
        if prop == "out" and value < commands.inPoint():
            return
        self._locked = True
        try:
            commands.setIntProperty("#RVFileSource.cut." + prop, [value], True)
            if self._sync_gui_in_out():
                if prop == "in":
                    commands.setInPoint(value)
                elif prop == "out":
                    commands.setOutPoint(value)
        except Exception:
            pass
        self._locked = False
        commands.redraw()

    def _finished_slot(self, prop: str) -> None:
        if self._cut_in_edit is None or self._cut_out_edit is None:
            return
        value = self._cut_in_edit.value() if prop == "in" else self._cut_out_edit.value()
        if value == -INT_MAX:
            return
        fs = commands.frameStart()
        fe = commands.frameEnd()
        if value < fs:
            value = fs
        if value > fe:
            value = fe
        if prop == "in" and value > commands.outPoint():
            value = commands.outPoint()
        if prop == "out" and value < commands.inPoint():
            value = commands.inPoint()
        self._locked = True
        try:
            if prop == "in" and self._cut_in_edit is not None:
                self._cut_in_edit.setValue(value)
            if prop == "out" and self._cut_out_edit is not None:
                self._cut_out_edit.setValue(value)
            commands.setIntProperty("#RVFileSource.cut." + prop, [value], True)
            if self._sync_gui_in_out():
                if prop == "in":
                    commands.setInPoint(value)
                elif prop == "out":
                    commands.setOutPoint(value)
        except Exception:
            pass
        self._locked = False
        commands.redraw()

    def _load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None or not mgr._panel_alive():
            return
        main_window = qtutils.sessionWindow()
        if self._ui is None:
            self._ui = load_ui_file("source.ui", main_window)
            if self._ui is None:
                return
            self._cut_in_edit = self._ui.findChild(QSpinBox, "cutInEdit")
            self._cut_out_edit = self._ui.findChild(QSpinBox, "cutOutEdit")
            self._reset_button = self._ui.findChild(QPushButton, "resetButton")
            self._sync_check_box = self._ui.findChild(QCheckBox, "syncCheckBox")
            if self._cut_in_edit is not None:
                self._cut_in_edit.setRange(-INT_MAX, INT_MAX)
                self._cut_in_edit.setSpecialValueText(" ")
                self._cut_in_edit.editingFinished.connect(lambda: self._finished_slot("in"))
                self._cut_in_edit.valueChanged.connect(
                    lambda v: self._changed_slot("in", v)
                )
            if self._cut_out_edit is not None:
                self._cut_out_edit.setRange(-INT_MAX, INT_MAX)
                self._cut_out_edit.setSpecialValueText(" ")
                self._cut_out_edit.editingFinished.connect(lambda: self._finished_slot("out"))
                self._cut_out_edit.valueChanged.connect(
                    lambda v: self._changed_slot("out", v)
                )
            if self._reset_button is not None:
                self._reset_button.clicked.connect(self._reset_slot)
            if self._sync_check_box is not None:
                self._sync_check_box.clicked.connect(self._sync_slot)
        if not ensure_editor(mgr, "Source", self._ui):
            return
        restore_edit_tab(mgr)
        self._update_ui()
        mgr.useEditor("Source")

    def _property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) < 1:
            event.reject()
            return
        node = parts[0]
        if not self._locked and commands.nodeType(node) == "RVFileSource":
            self._update_ui()
            if self._sync_gui_in_out():
                self._update_from_props()
        event.reject()

    def _new_in_point(self, event) -> None:
        prop = "#RVFileSource.cut.in"
        if not self._locked and self._sync_gui_in_out() and commands.propertyExists(prop):
            commands.setIntProperty(prop, [commands.inPoint()], True)
        event.reject()

    def _new_out_point(self, event) -> None:
        prop = "#RVFileSource.cut.out"
        if not self._locked and self._sync_gui_in_out() and commands.propertyExists(prop):
            commands.setIntProperty(prop, [commands.outPoint()], True)
        event.reject()

    def _update_from_props(self) -> None:
        self._locked = True
        try:
            cut_in = commands.getIntProperty("#RVFileSource.cut.in")[0]
            cut_out = commands.getIntProperty("#RVFileSource.cut.out")[0]
            fs = commands.frameStart()
            fe = commands.frameEnd()
            cut_in = min(max(cut_in, fs), fe)
            cut_out = min(max(cut_out, fs), fe)
            commands.setInPoint(cut_in)
            commands.setOutPoint(cut_out)
        except Exception:
            pass
        self._locked = False

    def activate(self) -> None:
        if self._sync_gui_in_out():
            self._update_from_props()
        rvtypes.MinorMode.activate(self)


def createMode():
    return SourceGroupEditMode()
