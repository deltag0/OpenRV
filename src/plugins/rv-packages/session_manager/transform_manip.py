#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Python port of transform_manip.mu — 2D transform manipulator for manual layout.
#
from __future__ import annotations

import math

from OpenGL.GL import *
from OpenGL.GLU import *

import rv.commands as commands
from rv import rvtypes

try:
    from PySide6.QtCore import Qt
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt


NO_CONTROL = 0
FREE_TRANSLATION = 1
TOP_LEFT_CORNER = 2
TOP_RIGHT_CORNER = 3
BOT_LEFT_CORNER = 4
BOT_RIGHT_CORNER = 5


def _set_property(prop_name: str, value) -> None:
    """Mirror Mu ``set()`` — create the property if needed, then write."""
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        if not commands.propertyExists(prop_name):
            commands.newProperty(prop_name, commands.IntType, 1)
        commands.setIntProperty(prop_name, [value], True)
    elif isinstance(value, float):
        if not commands.propertyExists(prop_name):
            commands.newProperty(prop_name, commands.FloatType, 1)
        commands.setFloatProperty(prop_name, [value], True)
    elif isinstance(value, str):
        if not commands.propertyExists(prop_name):
            commands.newProperty(prop_name, commands.StringType, 1)
        commands.setStringProperty(prop_name, [value], True)
    elif isinstance(value, list):
        if value and isinstance(value[0], (int, float)):
            if all(isinstance(v, int) for v in value):
                if not commands.propertyExists(prop_name):
                    commands.newProperty(prop_name, commands.IntType, len(value))
                commands.setIntProperty(prop_name, value, True)
            else:
                if not commands.propertyExists(prop_name):
                    commands.newProperty(prop_name, commands.FloatType, len(value))
                commands.setFloatProperty(prop_name, [float(v) for v in value], True)
        else:
            if not commands.propertyExists(prop_name):
                commands.newProperty(prop_name, commands.StringType, max(len(value), 1))
            commands.setStringProperty(prop_name, value, True)


def _mag(v) -> float:
    return math.hypot(v[0], v[1])


def _normalize(v):
    m = _mag(v)
    if m < 1e-10:
        return (0.0, 0.0)
    return (v[0] / m, v[1] / m)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _tag_value(tags, name: str):
    for t in tags or []:
        if isinstance(t, (list, tuple)) and len(t) >= 2:
            n, v = t[0], t[1]
        else:
            continue
        if n == name:
            return v
    return None


def _compute_gc(corners):
    gc = [0.0, 0.0]
    for c in corners:
        gc[0] += c[0]
        gc[1] += c[1]
    n = float(len(corners))
    return (gc[0] / n, gc[1] / n)


def _setup_projection(w, h, vflip: bool = False) -> None:
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    if vflip:
        gluOrtho2D(0.0, w - 1, h - 1, 0.0)
    else:
        gluOrtho2D(0.0, w - 1, 0.0, h - 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


def _draw_circle_fan(x, y, w, start, end, ainc, outline: bool = False) -> None:
    a0 = start * math.pi * 2.0
    a1 = end * math.pi * 2.0
    if outline:
        glBegin(GL_LINE_STRIP)
    else:
        glBegin(GL_TRIANGLE_FAN)
        glVertex2f(x, y)
    a = a0
    while a < a1:
        glVertex2f(math.sin(a) * w + x, math.cos(a) * w + y)
        a += ainc
    glVertex2f(math.sin(a1) * w + x, math.cos(a1) * w + y)
    glEnd()


def _circle_glyph(outline: bool = False) -> None:
    _draw_circle_fan(0.0, 0.0, 0.5, 0.0, 1.0, 0.3, outline)


def _triangle_glyph(outline: bool = False) -> None:
    if outline:
        glBegin(GL_LINE_LOOP)
    else:
        glBegin(GL_TRIANGLES)
    glVertex2f(-0.5, 0.0)
    glVertex2f(0.5, -0.5)
    glVertex2f(0.5, 0.5)
    glEnd()


def _tform_circle(outline: bool) -> None:
    glPushMatrix()
    glScalef(0.2333, 0.2333, 0.2333)
    _circle_glyph(outline)
    glPopMatrix()


def _tform_triangle(angle: float, outline: bool) -> None:
    glPushMatrix()
    glRotatef(angle, 0.0, 0.0, 1.0)
    glScalef(0.25, 0.25, 0.25)
    glTranslatef(-1.3, 0.0, 0.0)
    _triangle_glyph(outline)
    glPopMatrix()


def _translate_icon_glyph(outline: bool = False) -> None:
    _tform_circle(outline)
    for angle in (0.0, 90.0, 180.0, 270.0):
        _tform_triangle(angle, outline)


def _color_components(c, alpha_scale: float = 1.0):
    if hasattr(c, "r"):
        return (c.r, c.g, c.b, c.a * alpha_scale)
    if isinstance(c, (list, tuple)):
        if len(c) >= 4:
            return (c[0], c[1], c[2], c[3] * alpha_scale)
        if len(c) == 3:
            return (c[0], c[1], c[2], alpha_scale)
    return (1.0, 1.0, 1.0, alpha_scale)


def _node_aspect(node: str) -> float:
    geom = commands.nodeImageGeometry(node, commands.frame())
    pa = geom["pixelAspect"]
    xps = pa if pa > 1.0 else 1.0
    yps = pa if pa < 1.0 else 1.0
    return (geom["width"] * xps) / (geom["height"] / yps)


class TransformManip(rvtypes.MinorMode):
    def __init__(self) -> None:
        rvtypes.MinorMode.__init__(self)
        self._edit_nodes: list[dict] = []
        self._current_edit_node = None
        self._control = NO_CONTROL
        self._gc = (0.0, 0.0)
        self._corner = (0.0, 0.0)
        self._down_point = (0.0, 0.0)
        self._editing = False
        self._did_drag = False

        layout_menu = [
            ("Layout", [
                ("_", None),
                (
                    "Fit All Images",
                    self._fit_all,
                    None,
                    lambda: commands.NeutralMenuState,
                ),
                (
                    "Reset All Manips",
                    self._reset_all,
                    None,
                    lambda: commands.NeutralMenuState,
                ),
            ])
        ]

        self.init(
            "transform_manip",
            None,
            [
                ("pointer--move", self._move, "Search for Image"),
                ("pointer-1--push", self._push, "Grab Tile"),
                ("pointer-1--drag", self._drag, "Move/Scale Tile"),
                ("pointer-1--release", self._release, ""),
                (
                    "graph-node-inputs-changed",
                    self._node_inputs_changed,
                    "Update session UI",
                ),
                ("after-graph-view-change", self._after_graph_view_change, "Update UI"),
                ("before-graph-view-change", self._before_graph_view_change, "Update UI"),
                ("stylus-pen--move", self._move, "Search for Nearest Edge"),
                ("stylus-pen--push", self._push, "Move"),
                ("stylus-pen--drag", self._drag, "Move"),
                ("stylus-pen--release", self._release, ""),
            ],
            layout_menu,
            "zza",
        )

    def _edit_node(self, name: str):
        for enode in self._edit_nodes:
            if enode["tformNode"] == name:
                return enode
        return None

    def _active_image_index(self) -> int:
        for img in commands.renderedImages():
            v = _tag_value(img.get("tags"), "tmanip_state")
            if v is not None and v != "":
                return img["index"]
        return -1

    def _set_manip_state(self, pair, value: str) -> None:
        if pair is not None:
            tform_node = pair["tformNode"]
            if commands.nodeExists(tform_node):
                _set_property(tform_node + ".tag.tmanip_state", value)

    def _control_at(self, index: int, event):
        corners = commands.imageGeometryByIndex(index)
        p = event.pointer()
        gc = _compute_gc(corners)

        for c in corners:
            v = _sub(p, c)
            if abs(v[0]) < 25 and abs(v[1]) < 25:
                if c[0] < gc[0]:
                    control = TOP_LEFT_CORNER if c[1] > gc[1] else BOT_LEFT_CORNER
                else:
                    control = TOP_RIGHT_CORNER if c[1] > gc[1] else BOT_RIGHT_CORNER
                return control, gc, c

        return FREE_TRANSLATION, gc, gc

    def _set_control_cursor(self, control: int) -> None:
        if control == TOP_RIGHT_CORNER or control == BOT_LEFT_CORNER:
            commands.setCursor(Qt.SizeBDiagCursor)
        elif control == TOP_LEFT_CORNER or control == BOT_RIGHT_CORNER:
            commands.setCursor(Qt.SizeFDiagCursor)
        elif control == FREE_TRANSLATION:
            commands.setCursor(Qt.OpenHandCursor)
        else:
            commands.setCursor(Qt.WhatsThisCursor)

    def _move(self, event) -> None:
        last = self._current_edit_node
        self._current_edit_node = None
        self._control = NO_CONTROL
        commands.setCursor(Qt.ArrowCursor)

        for p in commands.imagesAtPixel(event.pointer()):
            if p.get("inside"):
                v = _tag_value(p.get("tags"), "tmanip")
                if v is not None:
                    self._current_edit_node = self._edit_node(v)
                    self._set_manip_state(self._current_edit_node, "hover")
                    control, gc, corner = self._control_at(p["index"], event)
                    self._control = control
                    self._gc = gc
                    self._corner = corner
                    self._set_control_cursor(control)
                    break

        if last != self._current_edit_node:
            if last is not None:
                self._set_manip_state(last, "")
            commands.redraw()

        event.reject()

    def _push(self, event) -> None:
        if self._current_edit_node is not None:
            commands.setCursor(Qt.ClosedHandCursor)
            self._set_manip_state(self._current_edit_node, "editing")

            if self._active_image_index() == -1:
                return

            self._down_point = event.pointer()
            self._did_drag = False
            self._editing = True
            commands.redraw()

    def _drag(self, event) -> None:
        if self._current_edit_node is None:
            return

        index = self._active_image_index()
        commands.setCursor(Qt.ClosedHandCursor)

        if index == -1:
            return

        tform_node = self._current_edit_node["tformNode"]
        trans_prop = tform_node + ".transform.translate"
        scale_prop = tform_node + ".transform.scale"
        trans = commands.getFloatProperty(trans_prop)
        scale = commands.getFloatProperty(scale_prop)
        corners = commands.imageGeometryByIndex(index)
        a, b, _, d = corners[0], corners[1], corners[2], corners[3]
        pp = event.pointer()
        dp = self._down_point
        ip = _sub(pp, dp)
        ba = _mag(_sub(b, a))
        da = _mag(_sub(d, a))
        aspect = ba / da if da else 1.0
        dx = ip[0] / ba * scale[0] * aspect if ba else 0.0
        dy = ip[1] / da * scale[1] if da else 0.0
        diag_dir = _normalize(_sub(self._corner, self._gc))
        diag_dist = _dot(_sub(pp, self._gc), diag_dir)
        down_dist = _dot(_sub(self._down_point, self._gc), diag_dir)
        diff = diag_dist - down_dist
        scl = (diag_dist - diff / 2.0) / down_dist if down_dist else 1.0
        sv = (diff * diag_dir[0], diff * diag_dir[1])
        sdx = sv[0] / ba * scale[0] * aspect if ba else 0.0
        sdy = sv[1] / da * scale[1] if da else 0.0

        if self._control == FREE_TRANSLATION:
            _set_property(trans_prop, [trans[0] + dx, trans[1] + dy])
        else:
            _set_property(trans_prop, [trans[0] + sdx / 2.0, trans[1] + sdy / 2.0])
            new_scale = max(scale[0] * scl, 0.01)
            _set_property(scale_prop, [new_scale, scale[1] * new_scale / scale[0]])

        self._down_point = pp
        self._did_drag = True
        commands.redraw()

    def _release(self, event) -> None:
        if self._editing:
            self._set_manip_state(self._current_edit_node, "hover")
            commands.setCursor(Qt.OpenHandCursor)
        else:
            commands.setCursor(Qt.ArrowCursor)

        self._did_drag = False
        self._editing = False

    def _reset_all(self, event) -> None:
        for enode in self._edit_nodes:
            tform_node = enode["tformNode"]
            _set_property(tform_node + ".transform.translate", [0.0, 0.0])
            _set_property(tform_node + ".transform.scale", [1.0, 1.0])
            _set_property(tform_node + ".transform.rotate", [0.0])
        commands.redraw()

    def _fit_all(self, event) -> None:
        aspect = _node_aspect(commands.viewNode())
        for enode in self._edit_nodes:
            tform_node = enode["tformNode"]
            inaspect = _node_aspect(tform_node)
            s = aspect / inaspect if inaspect else 1.0
            _set_property(tform_node + ".transform.translate", [0.0, 0.0])
            _set_property(tform_node + ".transform.scale", [s, s])
            _set_property(tform_node + ".transform.rotate", [0.0])
        commands.redraw()

    def _remove_tags(self) -> None:
        for x in self._edit_nodes:
            node = x["tformNode"]
            for prop in (node + ".tag.tmanip", node + ".tag.tmanip_state"):
                if commands.propertyExists(prop):
                    commands.deleteProperty(prop)

    def _find_editing_nodes(self, set_states: bool = True) -> None:
        vnode = commands.viewNode()
        infos = commands.metaEvaluateClosestByType(commands.frame(), "RVTransform2D")
        ins, _outs = commands.nodeConnections(vnode, False)

        if len(infos) != len(ins):
            self._edit_nodes = []
            return

        self._edit_nodes = []
        for i, info in enumerate(infos):
            tform_node = info["node"]
            pname = tform_node + ".tag.tmanip"
            sname = tform_node + ".tag.tmanip_state"
            self._edit_nodes.append({"tformNode": tform_node, "inputNode": ins[i]})
            if set_states or not commands.propertyExists(pname):
                _set_property(pname, tform_node)
                _set_property(sname, "")

    def _node_inputs_changed(self, event) -> None:
        node = event.contents()
        vnode = commands.viewNode()
        if vnode is not None and node == vnode:
            self._find_editing_nodes(set_states=False)
        event.reject()

    def _after_graph_view_change(self, event) -> None:
        self._find_editing_nodes()
        event.reject()

    def _before_graph_view_change(self, event) -> None:
        self._remove_tags()
        event.reject()

    def activate(self) -> None:
        self._find_editing_nodes()

    def deactivate(self) -> None:
        commands.setCursor(Qt.ArrowCursor)
        self._remove_tags()

    def _draw_corners(self, corners, mult: float, width: float) -> None:
        for i in range(len(corners)):
            i0 = 3 if i == 0 else i - 1
            i1 = (i + 1) % 4
            c = corners[i]
            c0 = corners[i0]
            c1 = corners[i1]
            m0 = _mag(_sub(c0, c))
            m1 = _mag(_sub(c1, c))
            dir0 = (c0[0] - c[0], c0[1] - c[1])
            dir0 = (dir0[0] / m0, dir0[1] / m0) if m0 else (0.0, 0.0)
            dir1 = (c1[0] - c[0], c1[1] - c[1])
            dir1 = (dir1[0] / m1, dir1[1] / m1) if m1 else (0.0, 0.0)
            nmult = 0.0 if (m1 / 2.0 < mult or m0 / 2.0 < mult) else mult

            glBegin(GL_LINES)
            glVertex2f(c[0] + dir0[0] * nmult, c[1] + dir0[1] * nmult)
            glVertex2f(c[0] - dir0[0] * width, c[1] - dir0[1] * width)
            glVertex2f(c[0] + dir1[0] * nmult, c[1] + dir1[1] * nmult)
            glVertex2f(c[0] - dir1[0] * width, c[1] - dir1[1] * width)
            glEnd()

    def render(self, event) -> None:
        if self._current_edit_node is None:
            return

        domain = event.domain()
        index = self._active_image_index()
        if index == -1:
            return

        _setup_projection(domain[0], domain[1], event.domainVerticalFlip())

        try:
            state = commands.data()
            bg = state.config.bg
            fg = state.config.fg

            corners = commands.imageGeometryByIndex(index)
            gc = _compute_gc(corners)
            self._gc = gc

            glEnable(GL_BLEND)
            glEnable(GL_LINE_SMOOTH)
            glEnable(GL_POINT_SMOOTH)
            glLineWidth(2.0)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            glColor4f(1.0, 1.0, 1.0, 0.5)
            glBegin(GL_LINE_LOOP)
            for c in corners:
                glVertex2f(c[0], c[1])
            glEnd()

            glColor4f(0.0, 0.0, 0.0, 0.5)
            glLineWidth(8.0)
            self._draw_corners(corners, 25.0, 0.0)
            glLineWidth(6.0)
            glColor4f(1.0, 1.0, 1.0, 0.5)
            self._draw_corners(corners, 25.0, 0.0)

            glLineWidth(1.5)

            bg_half = _color_components(bg, 0.5)
            glPushMatrix()
            glTranslatef(gc[0], gc[1], 0.0)
            glScalef(25.0, 25.0, 25.0)
            glColor4f(*bg_half)
            _circle_glyph(False)
            _circle_glyph(True)
            glPopMatrix()

            fg_rgba = _color_components(fg, 1.0)
            fg_half = _color_components(fg, 0.5)
            glPushMatrix()
            glTranslatef(gc[0], gc[1], 0.0)
            glScalef(25.0, 25.0, 25.0)
            glColor4f(*fg_rgba)
            _translate_icon_glyph(False)
            glColor4f(*fg_half)
            glLineWidth(1.0)
            _translate_icon_glyph(True)
            glPopMatrix()

            glDisable(GL_BLEND)
        except Exception:
            pass


def createMode():
    return TransformManip()
