#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as commands
import rv.rvtypes as rvtypes
import rv.runtime as runtime

from session_manager_support import set_property
from sm_edit_support import set_modes_active

g_the_mode = None


class StackGroupEditMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self.init(
            "StackGroup_edit_mode",
            None,
            [
                ("graph-state-change", self.property_changed, "Maybe update session UI"),
            ],
            [("Stack", [])],
            None,
        )

    @staticmethod
    def _sync_wipe_tags() -> None:
        """Match wipes.mu findEditingNodes tag properties for behavioral parity."""
        vnode = commands.viewNode()
        if vnode is None:
            return
        try:
            infos = commands.metaEvaluateClosestByType(commands.frame(), "RVTransform2D")
            ins = commands.nodeConnections(vnode, False)[0]
            if len(infos) != len(ins):
                return
            for i, info in enumerate(infos):
                node = info["node"] if isinstance(info, dict) else info.node
                set_property(node + ".tag.wipe", node)
                set_property(node + ".tag.wipe_name", ins[i])
        except Exception:
            pass

    @staticmethod
    def _toggle_wipe() -> None:
        try:
            import rvui

            rvui.toggleWipe()
        except Exception:
            try:
                runtime.eval("require rvui; rvui.toggleWipe();", ["rvui"])
            except Exception:
                pass

    def _activate_ui(self, on: bool) -> None:
        set_modes_active(["Composite_edit_mode", "Stack_edit_mode"], on)

        try:
            state = commands.data()
            wipe = getattr(state, "wipe", None)
            vnode = commands.viewNode()
            prop = f"{vnode}.ui.wipes" if vnode else None

            if on:
                if prop and commands.propertyExists(prop):
                    wipe_on = commands.getIntProperty(prop)[0] == 1
                    if wipe_on:
                        if wipe is None or not getattr(wipe, "_active", False):
                            self._toggle_wipe()
                        self._sync_wipe_tags()
                    elif wipe is not None and getattr(wipe, "_active", False):
                        wipe.toggle()
                elif wipe is not None and getattr(wipe, "_active", False):
                    wipe.toggle()
            elif wipe is not None and getattr(wipe, "_active", False):
                wipe.toggle()
        except Exception:
            pass

    def activate(self) -> None:
        self._activate_ui(True)

    def deactivate(self) -> None:
        self._activate_ui(False)

    def property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) < 3:
            event.reject()
            return

        comp = parts[1]
        name = parts[2]

        if comp == "ui" and name == "wipes":
            self._activate_ui(True)
            commands.redraw()
            event.reject()
            return

        if comp == "timing" and name == "retimeToOutput":
            self._activate_ui(True)
            commands.redraw()

        event.reject()


def createMode():
    global g_the_mode
    g_the_mode = StackGroupEditMode()
    return g_the_mode


def theMode():
    return g_the_mode
