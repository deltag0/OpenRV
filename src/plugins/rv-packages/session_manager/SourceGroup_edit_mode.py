#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
import rv.rvtypes as rvtypes
import rv.runtime as runtime

from sm_edit_support import INT_MAX, load_ui_file, session_manager

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QCheckBox, QPushButton, QSpinBox, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QCheckBox, QPushButton, QSpinBox, QWidget

g_the_mode = None


class SourceGroupEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._locked = False
        self._ui = None
        self._cut_in_edit = None
        self._cut_out_edit = None
        self._sync_checkbox = None
        self._reset_button = None

        self.init(
            "SourceGroup_edit_mode",
            None,
            [
                ("new-in-point", self.new_in_point, "Update In Point"),
                ("new-out-point", self.new_out_point, "Update Out Point"),
                ("session-manager-load-ui", self.load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            self._menu(),
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
            commands.set("#RVFileSource.cut.in", -INT_MAX)
            commands.set("#RVFileSource.cut.out", INT_MAX)
        except Exception:
            pass
        self._locked = False
        self.update_ui()
        commands.redraw()

    def update_ui(self) -> None:
        if self._ui is None:
            return

        self._locked = True
        try:
            cut_in = commands.getIntProperty("#RVFileSource.cut.in")[0]
            cut_out = commands.getIntProperty("#RVFileSource.cut.out")[0]

            self._cut_in_edit.setValue(cut_in)
            self._cut_out_edit.setValue(cut_out if cut_out != INT_MAX else -INT_MAX)
            self._sync_checkbox.setCheckState(
                Qt.Checked if self._sync_gui_in_out() else Qt.Unchecked
            )
        except Exception:
            pass
        self._locked = False

    def _reset_slot(self, _checked: bool = False) -> None:
        self.reset()

    def sync_slot(self, checked: bool) -> None:
        if self._locked:
            return

        prop = "#RVFileSource.cut.syncGui"
        commands.set(prop, 1 if checked else 0)
        if checked:
            self._update_from_props()
        self.update_ui()

    def toggle_sync(self, _event) -> None:
        self.sync_slot(not self._sync_gui_in_out())

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
        commands.set("#RVFileSource.cut." + prop, value)
        try:
            if self._sync_gui_in_out() and prop == "in":
                commands.setInPoint(value)
            if self._sync_gui_in_out() and prop == "out":
                commands.setOutPoint(value)
        except Exception:
            pass
        self._locked = False
        commands.redraw()

    def _finished_slot(self, prop: str) -> None:
        if self._cut_in_edit is None or self._cut_out_edit is None:
            return

        value = (
            self._cut_in_edit.value() if prop == "in" else self._cut_out_edit.value()
        )

        if value != -INT_MAX:
            if value < commands.frameStart():
                value = commands.frameStart()
            if value > commands.frameEnd():
                value = commands.frameEnd()
            if prop == "in" and value > commands.outPoint():
                value = commands.outPoint()
            if prop == "out" and value < commands.inPoint():
                value = commands.inPoint()

            self._locked = True
            if prop == "in":
                self._cut_in_edit.setValue(value)
            else:
                self._cut_out_edit.setValue(value)

            commands.set("#RVFileSource.cut." + prop, value)
            try:
                if self._sync_gui_in_out() and prop == "in":
                    commands.setInPoint(value)
                if self._sync_gui_in_out() and prop == "out":
                    commands.setOutPoint(value)
            except Exception:
                pass
            self._locked = False

        commands.redraw()

    def load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None:
            event.reject()
            return

        parent = qtutils.sessionWindow()

        if self._ui is None:
            self._ui = load_ui_file("source.ui", parent)
            if self._ui is None:
                event.reject()
                return

            self._cut_in_edit = self._ui.findChild(QSpinBox, "cutInEdit")
            if self._cut_in_edit is not None:
                self._cut_in_edit.setRange(-INT_MAX, INT_MAX)
                self._cut_in_edit.setSpecialValueText(" ")

            self._cut_out_edit = self._ui.findChild(QSpinBox, "cutOutEdit")
            if self._cut_out_edit is not None:
                self._cut_out_edit.setRange(-INT_MAX, INT_MAX)
                self._cut_out_edit.setSpecialValueText(" ")

            self._reset_button = self._ui.findChild(QPushButton, "resetButton")
            self._sync_checkbox = self._ui.findChild(QCheckBox, "syncCheckBox")

            mgr.addEditor("Source", self._ui)

            if self._reset_button is not None:
                self._reset_button.clicked.connect(self._reset_slot)
            if self._cut_in_edit is not None:
                self._cut_in_edit.editingFinished.connect(
                    lambda: self._finished_slot("in")
                )
                self._cut_in_edit.valueChanged.connect(
                    lambda v: self._changed_slot("in", v)
                )
            if self._cut_out_edit is not None:
                self._cut_out_edit.editingFinished.connect(
                    lambda: self._finished_slot("out")
                )
                self._cut_out_edit.valueChanged.connect(
                    lambda v: self._changed_slot("out", v)
                )
            if self._sync_checkbox is not None:
                self._sync_checkbox.clicked.connect(self.sync_slot)

        self.update_ui()
        mgr.useEditor("Source")
        event.reject()

    def property_changed(self, event) -> None:
        prop = event.contents()
        node = prop.split(".")[0]
        if not self._locked and commands.nodeType(node) == "RVFileSource":
            self.update_ui()
            if self._sync_gui_in_out():
                self._update_from_props()
        event.reject()

    def set_cut_value(self, prop: str, text: str) -> None:
        commands.set("#RVFileSource.cut." + prop, int(text))
        commands.redraw()

    def reset_cut(self, _event) -> None:
        self.reset()

    def new_in_point(self, event) -> None:
        prop = "#RVFileSource.cut.in"
        if not self._locked and self._sync_gui_in_out() and commands.propertyExists(prop):
            commands.set(prop, commands.inPoint())
        event.reject()

    def new_out_point(self, event) -> None:
        prop = "#RVFileSource.cut.out"
        if not self._locked and self._sync_gui_in_out() and commands.propertyExists(prop):
            commands.set(prop, commands.outPoint())
        event.reject()

    def _update_from_props(self) -> None:
        self._locked = True
        try:
            cut_in = commands.getIntProperty("#RVFileSource.cut.in")[0]
            cut_out = commands.getIntProperty("#RVFileSource.cut.out")[0]
            cut_in = min(max(cut_in, commands.frameStart()), commands.frameEnd())
            cut_out = min(max(cut_out, commands.frameStart()), commands.frameEnd())
            commands.setInPoint(cut_in)
            commands.setOutPoint(cut_out)
        except Exception:
            pass
        self._locked = False

    def activate(self) -> None:
        if self._sync_gui_in_out():
            self._update_from_props()
        rvtypes.MinorMode.activate(self)

    def sync_state(self):
        return (
            commands.CheckedMenuState
            if self._sync_gui_in_out()
            else commands.UncheckedMenuState
        )

    def source_menu_state(self):
        return commands.NeutralMenuState

    def set_cut_in_mode(self, _event) -> None:
        cut_in = commands.getIntProperty("#RVFileSource.cut.in")[0]
        runtime.eval(
            """
            {
                use rvui;
                use commands;
                let mode = startTextEntryMode(
                    \\: (string;) {
                        if (%d == -2147483648) return "Set Source In Point:";
                        else return "Set Source In Point (current=%%d):" %% %d;
                    },
                    \\: (void; string text) {
                        set("#RVFileSource.cut.in", int(text));
                        redraw();
                    });
                mode(nil);
            }
            """
            % (cut_in, cut_in),
            ["rvui", "commands"],
        )

    def set_cut_out_mode(self, _event) -> None:
        cut_out = commands.getIntProperty("#RVFileSource.cut.out")[0]
        runtime.eval(
            """
            {
                use rvui;
                use commands;
                let mode = startTextEntryMode(
                    \\: (string;) {
                        if (%d == 2147483647) return "Set Source Out Point:";
                        else return "Set Source Out Point (current=%%d):" %% %d;
                    },
                    \\: (void; string text) {
                        set("#RVFileSource.cut.out", int(text));
                        redraw();
                    });
                mode(nil);
            }
            """
            % (cut_out, cut_out),
            ["rvui", "commands"],
        )

    def _menu(self):
        neutral = self.source_menu_state
        return [
            (
                "Source",
                [
                    ("Set Source Cut In ...", self.set_cut_in_mode, None, neutral),
                    ("Set Source Cut Out ...", self.set_cut_out_mode, None, neutral),
                    ("Clear Source Cut In/Out", self.reset_cut, None, neutral),
                    ("Sync GUI With Source Cut In/Out", self.toggle_sync, None, self.sync_state),
                ],
            )
        ]


def createMode():
    global g_the_mode
    g_the_mode = SourceGroupEditMode()
    return g_the_mode
