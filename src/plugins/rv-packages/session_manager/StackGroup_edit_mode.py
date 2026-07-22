#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
from rv import rvtypes

from sm_edit_support import set_mode_active, set_modes_active


class StackGroupEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self.init(
            "StackGroup_edit_mode",
            None,
            [("graph-state-change", self._property_changed, "Maybe update session UI")],
            None,
        )

    def _activate_ui(self, on: bool) -> None:
        set_modes_active(["Composite_edit_mode", "Stack_edit_mode"], on)
        if not on:
            try:
                state = commands.data()
                wipe = getattr(state, "wipe", None)
                if wipe is not None and wipe.isActive():
                    wipe.toggle()
            except Exception:
                pass
            return
        node = commands.viewNode()
        if node is None:
            return
        wipe_prop = node + ".ui.wipes"
        try:
            state = commands.data()
            wipe = getattr(state, "wipe", None)
            if commands.propertyExists(wipe_prop):
                wipe_on = commands.getIntProperty(wipe_prop)[0] == 1
                if wipe_on:
                    if wipe is None or not wipe.isActive():
                        commands.sendInternalEvent("toggle-wipe", "")
                elif wipe is not None and wipe.isActive():
                    wipe.toggle()
            elif wipe is not None and wipe.isActive():
                wipe.toggle()
        except Exception:
            pass

    def _property_changed(self, event) -> None:
        parts = event.contents().split(".")
        if len(parts) >= 3 and parts[1] in ("ui", "timing"):
            if parts[2] in ("wipes", "retimeToOutput"):
                self._activate_ui(True)
                commands.redraw()
        event.reject()

    def activate(self) -> None:
        self._activate_ui(True)

    def deactivate(self) -> None:
        self._activate_ui(False)


def createMode():
    return StackGroupEditMode()
