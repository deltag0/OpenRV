#
# Copyright (C) 2023  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
from pymu import MuSymbol

from OpenGL.GL import (
    GL_BLEND,
    GL_ENABLE_BIT,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_POINTS,
    GL_POINT_SMOOTH,
    GL_QUADS,
    GL_SRC_ALPHA,
    glBegin,
    glBlendFunc,
    glColor4f,
    glEnable,
    glEnd,
    glPopAttrib,
    glPushAttrib,
    glVertex2f,
)

import rv.commands as rvc
import rv.extra_commands as rvec
import rv.rvtypes as rvt

_setup_projection = MuSymbol("rvui.setupProjection")
_expand_name_value_pairs = MuSymbol("glyph.expandNameValuePairs")
_name_value_pair_bounds = MuSymbol("glyph.nameValuePairBounds")
_draw_name_value_pairs = MuSymbol("glyph.drawNameValuePairs")
_draw_close_button = MuSymbol("glyph.drawCloseButton")
_gltext_size = MuSymbol("gltext.size")
_gltext_ascender_height = MuSymbol("gltext.ascenderHeight")
_gltext_descender_depth = MuSymbol("gltext.descenderDepth")
_session_data = MuSymbol("commands.data")


def _source_info_from_collection(info):
    if not info:
        return None, None

    front = info[0]
    if isinstance(front, dict):
        return front.get("name"), front.get("node")

    return front.name, front.node


def _pixel_source_info():
    state = _session_data()
    return _source_info_from_collection(state.pixelInfo)


def _rendered_source_info():
    return _source_info_from_collection(rvec.sourcesRendered())


def _source_layers(iname):
    if not iname:
        return []

    try:
        media = rvc.sourceMedia(iname)
    except Exception:
        return []

    if not media:
        return []

    if isinstance(media, dict):
        layers = media.get("layers") or media.get("_1")
    else:
        layers = media[1]

    return list(layers) if layers else []


class LayerSelect(rvt.Widget):
    def __init__(self):
        rvt.Widget.__init__(self)

        self._activeLayerIndex = 0
        self._selectLayerIndex = 0
        self._default = True
        self._th = 0.0
        self._nLayers = 0
        self._tbox = (0.0, 0.0)
        self._nw = 0.0
        self._drawInMargin = bool(rvc.readSettings("LayerSelect", "widgetIsDocked", True))

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
                ("pointer--wheelup", self._select_layer(1), "Choose Previous Layer"),
                ("pointer--wheeldown", self._select_layer(-1), "Choose Next Layer"),
                ("pointer-3--push", self.popupOpts, "Popup Selector Options"),
                ("pointer-2--push", self.setSelectedLayer, "Set Selected Layer"),
            ],
            None,
        )

        self._x = 40
        self._y = 60
        self._activeLayerIndex = self._selectLayerIndex = 0

        if self._drawInMargin:
            self.drawInMargin(0)

    def _select_layer(self, incr):
        def handler(event):
            idx = self._selectLayerIndex - incr
            if 0 <= idx < self._nLayers:
                self._selectLayerIndex = idx

            rvc.redraw()
            self._drawOnPresentation = True

        return handler

    def setSelectedLayer(self, event):
        iname, node = _pixel_source_info()
        if not iname:
            return

        layers = _source_layers(iname)

        try:
            if self._selectLayerIndex == 0:
                value = []
            else:
                value = ["layer", "", layers[self._selectLayerIndex - 1]]

            rvc.setStringProperty("%s.request.imageComponent" % node, value, True)
            self._activeLayerIndex = self._selectLayerIndex
        except Exception as exc:
            print("")
            print(exc)
            print("")

        rvc.redraw()

    def eventToIndex(self, p):
        state = _session_data()
        margin = state.config.bevelMargin
        return self._nLayers - int(((p[1] - self._y + margin) / self._th)) + 1

    def releaseSelect(self, event):
        state = _session_data()
        margin = state.config.bevelMargin

        rx = event.relativePointer()[0]
        if margin < rx < self._tbox[0] + margin:
            di = self.eventToIndex(self._downPoint)
            if 0 <= di < self._nLayers:
                self._selectLayerIndex = di
                self.setSelectedLayer(event)

        self.release(event, None)

    def handleMotion(self, event):
        gp = event.pointer()

        if not self.contains(gp):
            if self._default:
                self._selectLayerIndex = 0
            else:
                self._selectLayerIndex = self._activeLayerIndex + 1
        else:
            di = self.eventToIndex(event.pointer())
            if 0 <= di < self._nLayers:
                self._selectLayerIndex = di

        state = _session_data()
        domain = event.subDomain()
        p = event.relativePointer()
        tl = (0.0, domain[1])
        pc = (p[0] - tl[0], p[1] - tl[1])
        d = (pc[0] * pc[0] + pc[1] * pc[1]) ** 0.5
        m = state.config.bevelMargin
        lc = self._inCloseArea
        near = d < m

        if near != lc:
            rvc.redraw()
        self._inCloseArea = near

        rvc.redraw()

    def optFloatingSelector(self, event):
        self._drawInMargin = not self._drawInMargin
        rvc.writeSettings("LayerSelect", "widgetIsDocked", self._drawInMargin)

        if self._drawInMargin:
            self.drawInMargin(0)
        else:
            self.drawInMargin(-1)
            m = [-1.0, -1.0, -1.0, -1.0]
            m[0] = 0.0
            rvc.setMargins(tuple(m), True)

        rvc.redraw()

    def isFloatingSelector(self):
        if self._drawInMargin:
            return rvc.UncheckedMenuState
        return rvc.CheckedMenuState

    def popupOpts(self, event):
        disabled = lambda: rvc.DisabledMenuState
        rvc.popupMenu(
            event,
            [
                ("Layer Selector", None, None, disabled),
                ("_", None),
                (
                    "Floating Selector",
                    self.optFloatingSelector,
                    None,
                    self.isFloatingSelector,
                ),
            ],
        )

    def render(self, event):
        state = _session_data()
        iname, node = _rendered_source_info()

        domain = event.domain()
        bg = state.config.bg
        fg = state.config.fg
        err = rvc.isCurrentFrameError()
        layers = _source_layers(iname)

        if not layers:
            return

        self._nLayers = len(layers) + 1

        attrs = []
        active_indices = []
        activelayer = ""

        try:
            img_comp = rvc.getStringProperty("%s.request.imageComponent" % node)
            if img_comp and len(img_comp) == 3 and img_comp[0] == "layer":
                activelayer = img_comp[2]
            else:
                activelayer = ""
        except Exception as exc:
            print(exc)

        for i in range(len(layers) - 1, -1, -1):
            attrs.append(("        ", layers[i]))
            if activelayer == layers[i]:
                active_indices.append(i)
                self._activeLayerIndex = i

        if activelayer == "":
            active_indices.append(-1)
            self._default = True
            self._activeLayerIndex = 0
        else:
            self._default = False

        attrs.append(("        ", "Default"))

        if err:
            bg = state.config.bgErr

        _gltext_size(state.config.infoTextSize)
        _setup_projection(domain[0], domain[1], event.domainVerticalFlip())

        margin = state.config.bevelMargin
        x = 0 if self._drawInMargin else self._x + margin
        v_margins = rvc.margins()
        expanded = _expand_name_value_pairs(attrs)
        nvb1 = _name_value_pair_bounds(expanded, margin)
        vs = rvc.viewSize()
        yspace = vs[1] - v_margins[3] - v_margins[2]
        midy = v_margins[3] + yspace / 2.0
        adjy = midy - nvb1[0][1] / 2.0
        target_y = max(v_margins[3] + margin, adjy + margin)
        target_w = nvb1[0][0] + 1.25 * margin

        if self._drawInMargin:
            self._y = target_y - margin
            w = max(v_margins[0], target_w)
            glColor4f(0.0, 0.0, 0.0, 1.0)
            glBegin(GL_QUADS)
            glVertex2f(0.0, vs[1] - v_margins[2])
            glVertex2f(w, vs[1] - v_margins[2])
            glVertex2f(w, v_margins[3])
            glVertex2f(0.0, v_margins[3])
            glEnd()

        y = self._y + margin
        nvb = _draw_name_value_pairs(
            expanded,
            fg,
            bg,
            x,
            y,
            margin,
            0,
            0,
            0,
            0,
            self._drawInMargin,
        )
        tbox = nvb[0]

        emin = (
            0.0 if self._drawInMargin else self._x,
            self._y,
        )
        emax = (
            emin[0] + tbox[0] + margin + (margin if self._drawInMargin else margin),
            emin[1] + tbox[1] + margin,
        )

        fa = int(_gltext_ascender_height())
        fd = int(_gltext_descender_depth())
        th = fa - fd
        gx = x + margin / 2.0

        self._th = th
        self._tbox = tbox
        self._nw = nvb[3]

        glPushAttrib(GL_ENABLE_BIT)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_POINT_SMOOTH)
        glPointSize(6.0)
        glBegin(GL_POINTS)

        glColor4f(0.75, 0.75, 0.15, 1.0)
        gy = y + th * (len(layers) - self._selectLayerIndex) + fd + th / 2.0 + 2.0
        glVertex2f(gx, gy)

        glColor4f(0.15, 0.75, 0.75, 1.0)
        for ai in active_indices:
            gy = y + th * (len(layers) - ai - 1) + fd + th / 2.0 + 2.0
            glVertex2f(gx, gy)

        glEnd()
        glPopAttrib()

        if self._inCloseArea:
            _draw_close_button(
                x - margin / 2.0,
                tbox[1] + y - margin - margin / 4.0,
                margin / 2.0,
                bg,
                fg,
            )

        self.updateBounds(emin, emax)


def createMode():
    return LayerSelect()
