#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Python port of the RV ``session_manager`` package (Mu -> Python migration).

BAREBONES SKELETON — the starting point for the AI migration loop. It registers the
``session_manager`` MinorMode so the ``RV_MODE_IMPL_session_manager=python`` toggle
loads it, but implements **no behavior yet**. The loop fills this in, one
``COVERAGE.md`` item at a time, until the golden scenarios pass both gates.

Load contract (from ``mode_manager.mu`` ``loadPythonEntry``):
  * importable as ``session_manager`` (RV imports by bare name via ``PyImport_Import``)
  * module-level ``createMode()`` returning an ``rvtypes.MinorMode`` instance

Where to look:
  * Behaviors to reproduce:  ``src/test/golden/session_manager/COVERAGE.md``
  * Verification method:     ``src/test/golden/VERIFICATION.md``
  * Mu source of truth:      ``session_manager.mu(.in)`` + ``*_edit_mode.mu`` (this dir)
  * Reusable Qt assets:      the ``.ui`` files here (load via ``QUiLoader``); icons via
                             the ``:images/`` Qt resource (already compiled into RvCommon)

Notes learned during baseline capture (apply these in the port):
  * ``setUIName`` / ``uiName`` live in ``rv.extra_commands``, NOT ``rv.commands``.
  * ``RVRetimeGroup`` accepts a single input (other group types take many).
  * ``prev/nextViewNode()`` walk the view *history* (back/forward), not ``viewNodes()``.
  * Opening the panel *after* ``clearSession()`` can crash RV — build panel, then clear.
"""

from rv import rvtypes, commands  # noqa: F401  (commands used as the port grows)

MODE_NAME = "session_manager"


class SessionManagerMode(rvtypes.MinorMode):
    """The Session Manager panel. Currently a no-op stub.

    The migration loop grows this to match the Mu original. See COVERAGE.md for the
    ordered inventory; roughly:
      A/B  build the QDockWidget panel + node tree (session_manager.ui)
      C/D  node creation (Add/Folder menus, dialogs) + view switching/nav
      E    Inputs tab (reorder / sort / delete)
      F    Edit tab + per-view edit modes
      I/K  toolbar, context menus, event bindings
    """

    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        # TODO(port §A): menu "Tools/Session Manager", shortcut "x", event "key-down--x".
        # TODO(port §K): the 16 global event bindings + internal events.
        # TODO(port §B/M1): construct the dock panel from session_manager.ui.
        self.init(
            MODE_NAME,
            [],     # TODO(port §K): global event bindings
            None,   # TODO(port §I): menu
        )


def createMode():
    "Required entry point — RV calls this to instantiate the mode."
    return SessionManagerMode()
