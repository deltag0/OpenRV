#
# Copyright (C) 2023  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import rv.commands as rvc
import rv.rvtypes as rvt

import layer_select_gl as lsgl


def _info_field(entry, field: str):
    if isinstance(entry, dict):
        return entry[field]
    return getattr(entry, field)


class LayerSelect(rvt.Widget):
    def __init__(self) -> None:
        rvt.Widget.__init__(self)
        self._active_layer_index = 0
        self._select_layer_index = 0
        self._default = True
        self._th = 0.0
        self._n_layers = 0
        self._tbox = (0.0, 0.0)
        self._nw = 0.0
        self.init(
            "LayerSelect",
            [
                ("pointer-1--push", self.storeDownPoint, ""),
                ("pointer--move", self.handleMotion, ""),
                ("pointer-1--release", self.releaseSelect, ""),
                ("pointer-1--drag", self.drag, "Move Widget"),
                ("stylus-pen--push", self.storeDownPoint, ""),
                ("stylus-pen--move", self.handleMotion, ""),
                ("stylus-pen--release", self.releaseSelect, ""),
                ("stylus-pen--drag", self.drag, "Move Widget"),
                ("pointer--wheelup", self._select_layer_up, "Choose Previous Layer"),
                ("pointer--wheeldown", self._select_layer_down, "Choose Next Layer"),
                ("pointer-3--push", self.popupOpts, "Popup Selector Options"),
                ("pointer-2--push", self.setSelectedLayer, "Set Selected Layer"),
            ],
            None,
        )

        self._x = 40
        self._y = 60
        self._inCloseArea = False
        self._active_layer_index = 0
        self._select_layer_index = 0
        self._draw_in_margin = bool(rvc.readSettings("LayerSelect", "widgetIsDocked", True))
        if self._draw_in_margin:
            self.drawInMargin(0)
        self._sync_render_state()

    def requiredMarginValue(self):
        """Match Mu ``Widget.requiredMarginValue`` (``devicePixelRatio`` on bounds)."""
        vs = rvc.viewSize()
        try:
            dpr = float(rvc.devicePixelRatio())
        except Exception:
            dpr = 1.0

        if self._whichMargin == -1:
            return 0.0
        if self._whichMargin == 0:
            return (self._x + self._w) * dpr
        if self._whichMargin == 1:
            return vs[0] - self._x * dpr
        if self._whichMargin == 2:
            return vs[1] - self._y * dpr
        if self._whichMargin == 3:
            return (self._y + self._h) * dpr
        return 0.0

    def _sync_render_state(self) -> None:
        rvc.writeSettings("LayerSelect", "selectLayerIndex", self._select_layer_index)
        rvc.writeSettings("LayerSelect", "inCloseArea", self._inCloseArea)
        rvc.writeSettings("LayerSelect", "widgetX", float(self._x))
        rvc.writeSettings("LayerSelect", "widgetY", float(self._y))
        rvc.writeSettings("LayerSelect", "widgetIsDocked", self._draw_in_margin)

    def _select_layer_up(self, event) -> None:
        self.selectLayer(event, 1)

    def _select_layer_down(self, event) -> None:
        self.selectLayer(event, -1)

    def selectLayer(self, event, incr: int) -> None:
        if self._source_info() is None:
            return

        idx = self._select_layer_index - incr
        if 0 <= idx < self._n_layers:
            self._select_layer_index = idx
        self._sync_render_state()
        rvc.redraw()

    def setSelectedLayer(self, event) -> None:
        src = self._source_info()
        if src is None:
            return
        iname, node = src

        media = rvc.sourceMedia(iname)
        layers = list(media[1]) if media else []
        prop = "%s.request.imageComponent" % node
        try:
            if self._select_layer_index == 0:
                value: list[str] = []
            else:
                value = ["layer", "", layers[self._select_layer_index - 1]]
            if not rvc.propertyExists(prop):
                rvc.newProperty(prop, rvc.StringType, 1)
            rvc.setStringProperty(prop, value, True)
            self._active_layer_index = self._select_layer_index
        except Exception:
            pass
        self._sync_render_state()
        rvc.redraw()

    def eventToIndex(self, p) -> int:
        margin = lsgl.bevel_margin()
        return self._n_layers - int(((p[1] - self._y + margin) / self._th)) + 1

    def releaseSelect(self, event) -> None:
        margin = lsgl.bevel_margin()
        rx = event.relativePointer()[0]
        if margin < rx < self._tbox[0] + margin:
            di = self.eventToIndex(self._downPoint)
            if 0 <= di < self._n_layers:
                self._select_layer_index = di
                self.setSelectedLayer(event)
        self.release(event, None)

    def handleMotion(self, event) -> None:
        gp = event.pointer()
        if not self.contains(gp):
            if self._default:
                self._select_layer_index = 0
            else:
                self._select_layer_index = self._active_layer_index + 1
        else:
            di = self.eventToIndex(event.pointer())
            if 0 <= di < self._n_layers:
                self._select_layer_index = di

        domain = event.subDomain()
        p = event.relativePointer()
        tl = (0.0, domain[1])
        pc = (p[0] - tl[0], p[1] - tl[1])
        d = (pc[0] * pc[0] + pc[1] * pc[1]) ** 0.5
        m = lsgl.bevel_margin()
        lc = self._inCloseArea
        near = d < m
        if near != lc:
            rvc.redraw()
        self._inCloseArea = near
        self._sync_render_state()
        rvc.redraw()

    def optFloatingSelector(self, event) -> None:
        self._draw_in_margin = not self._draw_in_margin
        rvc.writeSettings("LayerSelect", "widgetIsDocked", self._draw_in_margin)
        if self._draw_in_margin:
            self.drawInMargin(0)
        else:
            self.drawInMargin(-1)
            m = [-1.0, -1.0, -1.0, -1.0]
            m[0] = 0.0
            rvc.setMargins(tuple(m), True)
        self._sync_render_state()
        rvc.redraw()

    def isFloatingSelector(self):
        if self._draw_in_margin:
            return rvc.UncheckedMenuState
        return rvc.CheckedMenuState

    def _source_info(self) -> tuple[str, str] | None:
        """Rendered source (media name, graph node) for layer property writes."""
        sinfo = list(rvc.sourcesRendered())
        if not sinfo:
            return None
        entry = sinfo[0]
        name = _info_field(entry, "name")
        node = _info_field(entry, "node")
        if not name or not node:
            return None
        return name, node

    def drag(self, event) -> None:
        rvt.Widget.drag(self, event)
        self._sync_render_state()

    def popupOpts(self, event) -> None:
        def toggle(_event=None):
            self.optFloatingSelector(event)

        menu = [
            ("Layer Selector", None, "", lambda: rvc.DisabledMenuState),
            ("_", None),
            ("Floating Selector", toggle, "", self.isFloatingSelector),
        ]
        rvc.popupMenu(event, menu)

    def render(self, event) -> None:
        sinfo = list(rvc.sourcesRendered())
        if sinfo:
            media = rvc.sourceMedia(_info_field(sinfo[0], "name"))
            if media:
                self._n_layers = len(media[1]) + 1
        self._sync_render_state()
        layout = lsgl.render_layer_widget(event)
        if layout is None:
            return
        tbox_w, tbox_h, th, nw, emin, emax, widget_y = layout
        self._th = th
        self._tbox = (tbox_w, tbox_h)
        self._nw = nw
        if self._draw_in_margin:
            self._y = widget_y
        self.updateBounds(emin, emax)


def createMode():
    return LayerSelect()
