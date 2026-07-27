#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.rvtypes as rvtypes

from sm_edit_support import set_modes_active

g_the_mode = None


class SwitchGroupEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self.init("SwitchGroup_edit_mode", None, None, None, None)

    def _activate_ui(self, on: bool) -> None:
        set_modes_active(["Switch_edit_mode"], on)

    def activate(self) -> None:
        self._activate_ui(True)

    def deactivate(self) -> None:
        self._activate_ui(False)


def createMode():
    global g_the_mode
    g_the_mode = SwitchGroupEditMode()
    return g_the_mode
