#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
import rv.rvtypes as rvtypes
import rv.runtime as runtime

from sm_edit_support import load_ui_file, session_manager

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QSlider, QWidget
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import QComboBox, QLabel, QLineEdit, QSlider, QWidget

g_the_mode = None

_COMPOSITE_TYPES = [
    "over",
    "add",
    "dissolve",
    "difference",
    "-difference",
    "replace",
    "topmost",
]


class CompositeEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._ui = None
        self._combo_box = None
        self._dissolve_line_edit = None
        self._dissolve_label = None
        self._dissolve_slider = None

        self.init(
            "Composite_edit_mode",
            None,
            [
                ("session-manager-load-ui", self.load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            self._menu(),
            "b",
        )

    def set_op(self, index: int) -> None:
        name = _COMPOSITE_TYPES[index] if 0 <= index < len(_COMPOSITE_TYPES) else "over"
        commands.set("#RVStack.composite.type", name)
        self.update_ui()
        commands.redraw()

    def set_op_event(self, _event, index: int) -> None:
        self.set_op(index)

    def set_dissolve_amount(self) -> None:
        if self._dissolve_line_edit is None or self._dissolve_slider is None:
            return

        amount_text = self._dissolve_line_edit.text()
        try:
            amount = float(amount_text)
            amount = max(0.0, min(1.0, amount))
            self._dissolve_slider.setValue(int(amount * 100.0))
            commands.setFloatProperty("#RVStack.composite.dissolveAmount", [amount])
            commands.redraw()
        except Exception:
            self._dissolve_line_edit.setText("0.5")
            self._dissolve_slider.setValue(50)
            commands.setFloatProperty("#RVStack.composite.dissolveAmount", [0.5])
            commands.redraw()

    def set_dissolve_amount_from_slider(self, value: int) -> None:
        if self._dissolve_line_edit is None:
            return

        amount = float(value) / 100.0
        self._dissolve_line_edit.setText("%g" % amount)
        commands.setFloatProperty("#RVStack.composite.dissolveAmount", [amount])
        commands.redraw()

    def update_ui(self) -> None:
        if self._ui is None or self._combo_box is None:
            return

        try:
            current_type = commands.getStringProperty("#RVStack.composite.type")[0]
        except Exception:
            current_type = "over"

        try:
            index = _COMPOSITE_TYPES.index(current_type)
        except ValueError:
            index = len(_COMPOSITE_TYPES)

        self._combo_box.setCurrentIndex(index)

        show_dissolve = current_type == "dissolve"
        if self._dissolve_line_edit is not None:
            self._dissolve_line_edit.setVisible(show_dissolve)
        if self._dissolve_label is not None:
            self._dissolve_label.setVisible(show_dissolve)
        if self._dissolve_slider is not None:
            self._dissolve_slider.setVisible(show_dissolve)

        self._ui.adjustSize()
        self._ui.updateGeometry()
        self._ui.update()
        parent = self._ui.parentWidget()
        if parent is not None:
            parent.adjustSize()
            parent.update()

        if show_dissolve:
            try:
                amounts = commands.getFloatProperty("#RVStack.composite.dissolveAmount")
                if amounts:
                    amount = amounts[0]
                    if self._dissolve_line_edit is not None:
                        self._dissolve_line_edit.setText("%g" % amount)
                    if self._dissolve_slider is not None:
                        self._dissolve_slider.setValue(int(amount * 100.0))
            except Exception:
                if self._dissolve_line_edit is not None:
                    self._dissolve_line_edit.setText("0.5")
                if self._dissolve_slider is not None:
                    self._dissolve_slider.setValue(50)

    def property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) >= 3 and parts[1] == "composite" and parts[2] in (
            "type",
            "dissolveAmount",
        ):
            self.update_ui()
        event.reject()

    def load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None:
            event.reject()
            return

        parent = qtutils.sessionWindow()

        if self._ui is None:
            self._ui = load_ui_file("composite.ui", parent)
            if self._ui is None:
                event.reject()
                return

            self._combo_box = self._ui.findChild(QComboBox, "comboBox")
            self._dissolve_line_edit = self._ui.findChild(QLineEdit, "dissolveLineEdit")
            self._dissolve_label = self._ui.findChild(QLabel, "dissolveLabel")
            self._dissolve_slider = self._ui.findChild(QSlider, "dissolveSlider")

            if self._dissolve_line_edit is not None:
                self._dissolve_line_edit.setVisible(False)
            if self._dissolve_label is not None:
                self._dissolve_label.setVisible(False)
            if self._dissolve_slider is not None:
                self._dissolve_slider.setVisible(False)

            mgr.addEditor("Composite Function", self._ui)

            if self._combo_box is not None:
                self._combo_box.currentIndexChanged.connect(self.set_op)
            if self._dissolve_line_edit is not None:
                self._dissolve_line_edit.editingFinished.connect(self.set_dissolve_amount)
            if self._dissolve_slider is not None:
                self._dissolve_slider.valueChanged.connect(
                    self.set_dissolve_amount_from_slider
                )

        self.update_ui()
        mgr.useEditor("Composite Function")
        event.reject()

    def op_state(self, name: str):
        def state():
            try:
                op = commands.getStringProperty("#RVStack.composite.type")[0]
                return (
                    commands.CheckedMenuState
                    if op == name
                    else commands.UncheckedMenuState
                )
            except Exception:
                return commands.UncheckedMenuState

        return state

    def cycle_stack_forward(self, _event) -> None:
        runtime.eval("require rvui; rvui.cycleStackForward(nil);", ["rvui"])

    def cycle_stack_backward(self, _event) -> None:
        runtime.eval("require rvui; rvui.cycleStackBackward(nil);", ["rvui"])

    def is_stack_mode(self):
        def state():
            try:
                type_name = commands.nodeType(commands.viewNode())
                if type_name in ("RVStackGroup", "RVLayoutGroup"):
                    return commands.UncheckedMenuState
                return commands.DisabledMenuState
            except Exception:
                return commands.DisabledMenuState

        return state

    def _menu(self):
        items = [("Composite Operation", None, None, None)]
        labels = [
            "over",
            "add",
            "dissolve",
            "difference",
            "-difference",
            "replace",
            "topmost",
        ]
        for i, label in enumerate(labels):
            display = "   " + ("Inverted Difference" if label == "-difference" else label.title())
            if label == "over":
                display = "   Over"
            elif label == "add":
                display = "   Add"
            elif label == "dissolve":
                display = "   Dissolve"
            elif label == "difference":
                display = "   Difference"
            elif label == "replace":
                display = "   Replace"
            elif label == "topmost":
                display = "   Topmost"
            items.append(
                (
                    display,
                    lambda e, idx=i: self.set_op_event(e, idx),
                    None,
                    self.op_state(label),
                )
            )
        items.extend(
            [
                ("_", None),
                ("Cycle Forward", self.cycle_stack_forward, None, self.is_stack_mode()),
                ("Cycle Backward", self.cycle_stack_backward, None, self.is_stack_mode()),
            ]
        )
        return [("Stack", items)]


def createMode():
    global g_the_mode
    g_the_mode = CompositeEditMode()
    return g_the_mode
