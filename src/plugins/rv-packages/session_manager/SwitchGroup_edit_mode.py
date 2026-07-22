#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
from rv import rvtypes

from sm_edit_support import set_mode_active


class SwitchGroupEditMode(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self.init("SwitchGroup_edit_mode", None, None, None)

    def _activate_ui(self, on: bool) -> None:
        set_mode_active("Switch_edit_mode", on)

    def activate(self) -> None:
        self._activate_ui(True)

    def deactivate(self) -> None:
        self._activate_ui(False)


def createMode():
    return SwitchGroupEditMode()
