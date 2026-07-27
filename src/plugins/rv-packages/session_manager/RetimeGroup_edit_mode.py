#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.qtutils as qtutils
import rv.rvtypes as rvtypes
import rv.runtime as runtime

from sm_edit_support import checkbox_to_int, load_ui_file, session_manager

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QCheckBox,
        QLineEdit,
        QPushButton,
        QWidget,
    )
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtWidgets import (
        QCheckBox,
        QLineEdit,
        QPushButton,
        QWidget,
    )

g_the_mode = None


class RetimeGroupEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._ui = None
        self._fps_edit = None
        self._voffset_edit = None
        self._aoffset_edit = None
        self._vscale_edit = None
        self._ascale_edit = None
        self._reverse_button = None
        self._reset_button = None

        self.init(
            "RetimeGroup_edit_mode",
            None,
            [
                ("session-manager-load-ui", self.load_ui, "Load UI into Session Manager"),
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            self._menu(),
            None,
        )

    def reset(self) -> None:
        commands.set("#RVRetime.visual.scale", 1.0)
        commands.set("#RVRetime.visual.offset", 0.0)
        commands.set("#RVRetime.audio.scale", 1.0)
        commands.set("#RVRetime.audio.offset", 0.0)
        commands.redraw()

    def reverse(self) -> None:
        length = commands.frameEnd() - commands.frameStart()
        scl = commands.getFloatProperty("#RVRetime.visual.scale")[0]

        if scl < 0:
            commands.set("#RVRetime.visual.scale", 1.0)
            commands.set("#RVRetime.visual.offset", 0)
            commands.set("#RVRetime.audio.scale", 1.0)
            commands.set("#RVRetime.audio.offset", 0)
        else:
            commands.set("#RVRetime.visual.scale", -1.0)
            commands.set("#RVRetime.visual.offset", float(-length))
            commands.set("#RVRetime.audio.scale", 1.0)
            commands.set("#RVRetime.audio.offset", 0)

        commands.redraw()

    def update_ui(self) -> None:
        if self._ui is None:
            return

        try:
            fps = commands.getFloatProperty("#RVRetime.output.fps")[0]
            vscale = commands.getFloatProperty("#RVRetime.visual.scale")[0]
            ascale = commands.getFloatProperty("#RVRetime.audio.scale")[0]
            voffset = commands.getFloatProperty("#RVRetime.visual.offset")[0]
            aoffset = commands.getFloatProperty("#RVRetime.audio.offset")[0]
        except Exception:
            return

        self._fps_edit.setText("%g" % fps)
        self._vscale_edit.setText("%g" % vscale)
        self._ascale_edit.setText("%g" % ascale)
        self._voffset_edit.setText("%g" % voffset)
        self._aoffset_edit.setText("%g" % aoffset)

    def _reset_slot(self, _checked: bool = False) -> None:
        self.reset()

    def _reverse_slot(self, _checked: bool = False) -> None:
        self.reverse()

    def _edit_slot(self, line_edit: QLineEdit, prop: str) -> None:
        try:
            value = float(line_edit.text())
            commands.set("#RVRetime" + prop, value)
            if prop == ".output.fps":
                commands.setFPS(value)
            commands.redraw()
        except Exception:
            pass

    def load_ui(self, event) -> None:
        mgr = session_manager()
        if mgr is None:
            event.reject()
            return

        parent = qtutils.sessionWindow()

        if self._ui is None:
            self._ui = load_ui_file("retime.ui", parent)
            if self._ui is None:
                event.reject()
                return

            self._fps_edit = self._ui.findChild(QLineEdit, "fpsEdit")
            self._ascale_edit = self._ui.findChild(QLineEdit, "ascaleEdit")
            self._vscale_edit = self._ui.findChild(QLineEdit, "vscaleEdit")
            self._aoffset_edit = self._ui.findChild(QLineEdit, "aoffsetEdit")
            self._voffset_edit = self._ui.findChild(QLineEdit, "voffsetEdit")
            self._reset_button = self._ui.findChild(QPushButton, "resetButton")
            self._reverse_button = self._ui.findChild(QPushButton, "reverseButton")

            mgr.addEditor("Retime", self._ui)

            if self._reset_button is not None:
                self._reset_button.clicked.connect(self._reset_slot)
            if self._reverse_button is not None:
                self._reverse_button.clicked.connect(self._reverse_slot)

            for edit, prop in (
                (self._fps_edit, ".output.fps"),
                (self._ascale_edit, ".audio.scale"),
                (self._vscale_edit, ".visual.scale"),
                (self._aoffset_edit, ".audio.offset"),
                (self._voffset_edit, ".visual.offset"),
            ):
                if edit is not None:
                    edit.editingFinished.connect(lambda e=edit, p=prop: self._edit_slot(e, p))

        self.update_ui()
        mgr.useEditor("Retime")
        event.reject()

    def property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if parts and commands.nodeType(parts[0]) == "RVRetime":
            self.update_ui()
        event.reject()

    def _factor_prompt(self, invert: bool) -> str:
        factor = commands.getFloatProperty("#RVRetime.visual.scale")[0]
        shown = (1.0 / factor) if invert else factor
        label = "Slow Down by Factor" if invert else "Speed Up by Factor"
        return "%s (current=%g):" % (label, shown)

    def _set_factor_value(self, text: str, invert: bool) -> None:
        factor = (1.0 / float(text)) if invert else float(text)
        commands.set("#RVRetime.visual.scale", factor)
        commands.redraw()

    def _fps_prompt(self) -> str:
        fps = commands.getFloatProperty("#RVRetime.output.fps")[0]
        return "Convert to FPS (current=%g):" % fps

    def _set_convert_fps(self, text: str) -> None:
        new_fps = float(text)
        commands.set("#RVRetime.output.fps", new_fps)
        commands.setFPS(new_fps)

    def _start_text_entry(self, prompt: str, commit_mu: str) -> None:
        runtime.eval(
            """
            {
                use rvui;
                use commands;
                let mode = startTextEntryMode(
                    \\: (string;) { %s },
                    %s);
                mode(nil);
            }
            """
            % (prompt, commit_mu),
            ["rvui", "commands"],
        )

    def _start_parameter(self, param: str, scl: float, reset: float) -> None:
        runtime.eval(
            'require rvui; rvui.startParameterMode("%s", %g, %g)(nil);'
            % (param, scl, reset),
            ["rvui"],
        )

    def slow_down_factor(self, _event) -> None:
        factor = commands.getFloatProperty("#RVRetime.visual.scale")[0]
        runtime.eval(
            """
            {
                use rvui;
                use commands;
                let mode = startTextEntryMode(
                    \\: (string;) { "Slow Down by Factor (current=%g):" % (1.0 / %g); },
                    \\: (void; string text) {
                        set("#RVRetime.visual.scale", 1.0 / float(text));
                        redraw();
                    });
                mode(nil);
            }
            """
            % (factor, factor),
            ["rvui", "commands"],
        )

    def speed_up_factor(self, _event) -> None:
        factor = commands.getFloatProperty("#RVRetime.visual.scale")[0]
        runtime.eval(
            """
            {
                use rvui;
                use commands;
                let mode = startTextEntryMode(
                    \\: (string;) { "Speed Up by Factor (current=%g):" % %g; },
                    \\: (void; string text) {
                        set("#RVRetime.visual.scale", float(text));
                        redraw();
                    });
                mode(nil);
            }
            """
            % (factor, factor),
            ["rvui", "commands"],
        )

    def convert_to_fps(self, _event, new_fps: float) -> None:
        for _src in commands.sourcesRendered():
            commands.set("#RVRetime.output.fps", new_fps)
        commands.setFPS(new_fps)

    def reset_timing(self, _event) -> None:
        self.reset()

    def reverse_timing(self, _event) -> None:
        self.reverse()

    def edit_fps(self, _event) -> None:
        fps = commands.getFloatProperty("#RVRetime.output.fps")[0]
        runtime.eval(
            """
            {
                use rvui;
                use commands;
                let mode = startTextEntryMode(
                    \\: (string;) { "Convert to FPS (current=%g):" % %g; },
                    \\: (void; string text) {
                        let newFPS = float(text);
                        set("#RVRetime.output.fps", newFPS);
                        setFPS(newFPS);
                    });
                mode(nil);
            }
            """
            % (fps, fps),
            ["rvui", "commands"],
        )

    def _menu(self):
        enabled = lambda: commands.NeutralMenuState
        fps_items = [
            ("24", lambda e: self.convert_to_fps(e, 24.0), None, enabled),
            ("25", lambda e: self.convert_to_fps(e, 25.0), None, enabled),
            ("23.98", lambda e: self.convert_to_fps(e, 23.98), None, enabled),
            ("29.97", lambda e: self.convert_to_fps(e, 29.97), None, enabled),
            ("30", lambda e: self.convert_to_fps(e, 30.0), None, enabled),
            ("59.94", lambda e: self.convert_to_fps(e, 59.94), None, enabled),
            ("60", lambda e: self.convert_to_fps(e, 60.0), None, enabled),
            ("_", None),
            ("Custom...", self.edit_fps, None, enabled),
        ]
        return [
            (
                "Retime",
                [
                    ("Convert to FPS", fps_items),
                    ("_", None),
                    ("Slow Down by Factor...", self.slow_down_factor, None, enabled),
                    ("Speed Up By Factor...", self.speed_up_factor, None, enabled),
                    ("Reverse", self.reverse_timing, None, enabled),
                    ("_", None),
                    ("Edit Raw", None, None, None),
                    (
                        "    Visual Scale...",
                        lambda e: self._start_parameter("#RVRetime.visual.scale", 0.05, 1.0),
                        None,
                        enabled,
                    ),
                    (
                        "    Visual Offset...",
                        lambda e: self._start_parameter("#RVRetime.visual.offset", 0.05, 0.0),
                        None,
                        enabled,
                    ),
                    (
                        "    Audio Scale...",
                        lambda e: self._start_parameter("#RVRetime.audio.scale", 0.05, 1.0),
                        None,
                        enabled,
                    ),
                    (
                        "    Audio Offset...",
                        lambda e: self._start_parameter("#RVRetime.audio.offset", 0.05, 0.0),
                        None,
                        enabled,
                    ),
                    ("_", None),
                    ("Reset Timing", self.reset_timing, None, enabled),
                ],
            )
        ]


def createMode():
    global g_the_mode
    g_the_mode = RetimeGroupEditMode()
    return g_the_mode
