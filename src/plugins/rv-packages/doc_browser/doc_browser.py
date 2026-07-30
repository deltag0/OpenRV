#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Python port of the RV ``doc_browser`` package.

The Mu symbol-introspection stack (``DocModel``, HTML rendering, ``QWebEngineView``)
remains in ``doc_browser.mu`` (``DocBrowserUI`` + bridge functions) and is driven through
``rv.runtime.eval`` until a native Python symbol API exists.  ``asciidoc_to_html.py`` is ported; the Mu module
still uses its embedded copy for pixel parity during migration.
"""

from __future__ import annotations

import rv.rvtypes as rvtypes
import rv.runtime as runtime

_MU_MODULES = ["doc_browser", "runtime", "commands", "rvtypes"]
_mu_ready = False


def _ensure_mu() -> None:
    global _mu_ready
    if not _mu_ready:
        runtime.eval("require doc_browser; doc_browser.initMode();", _MU_MODULES)
        _mu_ready = True


def _mu_activate() -> None:
    _ensure_mu()
    runtime.eval("doc_browser.modeActivate();", _MU_MODULES)


def _mu_deactivate() -> None:
    if not _mu_ready:
        return
    runtime.eval("doc_browser.modeDeactivate();", _MU_MODULES)


def _mu_session_close() -> None:
    if not _mu_ready:
        return
    runtime.eval("doc_browser.modeSessionClose();", _MU_MODULES)


class DocBrowserMode(rvtypes.MinorMode):
    """Interactive Mu API documentation browser (Python MinorMode shell)."""

    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self.init(
            "doc_browser",
            [("before-session-deletion", self._on_before_session_deletion, "Close browser")],
            None,
            None,
            "z",
            9,
        )

    def _on_before_session_deletion(self, event) -> None:
        _mu_session_close()
        event.reject()

    def activate(self) -> None:
        rvtypes.MinorMode.activate(self)
        _mu_activate()

    def deactivate(self) -> None:
        rvtypes.MinorMode.deactivate(self)
        _mu_deactivate()


def createMode() -> DocBrowserMode:
    return DocBrowserMode()
