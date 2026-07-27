#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import math

import rv.commands as commands
import rv.rvtypes as rvtypes
from session_manager_support import set_property

try:
    from PySide6.QtCore import Qt
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt

from OpenGL.GL import (
    GL_BLEND,
    GL_LINE_LOOP,
    GL_LINES,
    GL_LINE_SMOOTH,
    GL_MODELVIEW,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_POINT_SMOOTH,
    GL_PROJECTION,
    GL_SRC_ALPHA,
    GL_TRIANGLE_FAN,
    glRotatef,
    glBegin,
    glBlendFunc,
    glColor4f,
    glDisable,
    glEnable,
    glEnd,
    glLineWidth,
    glLoadIdentity,
    glMatrixMode,
    glPopMatrix,
    glPushMatrix,
    glScalef,
    glTranslatef,
    glVertex2f,
)
from OpenGL.GLU import gluOrtho2D

g_the_mode = None


def _mag(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _normalize(v):
    length = math.hypot(v[0], v[1])
    if length == 0:
        return (0.0, 0.0)
    return (v[0] / length, v[1] / length)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _compute_gc(corners):
    gc = [0.0, 0.0]
    for c in corners:
        gc[0] += c[0]
        gc[1] += c[1]
    count = float(len(corners))
    return (gc[0] / count, gc[1] / count)


def _tag_value(tags, name):
    for tag in tags:
        if tag[0] == name:
            return tag[1]
    return None


def _draw_circle_fan(outline: bool) -> None:
    segments = 32
    if outline:
        glBegin(GL_LINE_LOOP)
    else:
        glBegin(GL_TRIANGLE_FAN)
    glVertex2f(0.0, 0.0)
    for i in range(segments + 1):
        angle = (float(i) / float(segments)) * 2.0 * math.pi
        glVertex2f(0.5 * math.cos(angle), 0.5 * math.sin(angle))
    glEnd()


def _triangle_glyph(outline: bool) -> None:
    if outline:
        glBegin(GL_LINE_LOOP)
    else:
        glBegin(GL_TRIANGLE_FAN)
    glVertex2f(-0.5, 0.0)
    glVertex2f(0.5, -0.5)
    glVertex2f(0.5, 0.5)
    glEnd()


def _translate_icon_glyph(outline: bool) -> None:
    glPushMatrix()
    glScalef(0.2333, 0.2333, 0.2333)
    _draw_circle_fan(outline)
    glPopMatrix()

    for angle in (0.0, 90.0, 180.0, 270.0):
        glPushMatrix()
        glRotatef(angle, 0.0, 0.0, 1.0)
        glScalef(0.25, 0.25, 0.25)
        glTranslatef(-1.3, 0.0, 0.0)
        _triangle_glyph(outline)
        glPopMatrix()


class TransformManip(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._edit_nodes = []
        self._current_edit_node = None
        self._control = "NoControl"
        self._gc = (0.0, 0.0)
        self._corner = (0.0, 0.0)
        self._down_point = (0.0, 0.0)
        self._editing = False
        self._did_drag = False

        self.init(
            "transform_manip",
            None,
            [
                ("pointer--move", self.move, "Search for Image"),
                ("pointer-1--push", self.push, "Grab Tile"),
                ("pointer-1--drag", self.drag, "Move/Scale Tile"),
                ("pointer-1--release", self.release, ""),
                ("graph-node-inputs-changed", self.node_inputs_changed, "Update session UI"),
                ("after-graph-view-change", self.after_graph_view_change, "Update UI"),
                ("before-graph-view-change", self.before_graph_view_change, "Update UI"),
                ("graph-state-change", self.graph_state_change, "Sync tags on layout mode change"),
                ("stylus-pen--move", self.move, "Search for Nearest Edge"),
                ("stylus-pen--push", self.push, "Move"),
                ("stylus-pen--drag", self.drag, "Move"),
                ("stylus-pen--release", self.release, ""),
            ],
            [
                (
                    "Layout",
                    [
                        ("_", None),
                        ("Fit All Images", self.fit_all, None, lambda: commands.NeutralMenuState),
                        ("Reset All Manips", self.reset_all, None, lambda: commands.NeutralMenuState),
                    ],
                )
            ],
            "zza",
        )

    def _edit_node(self, name):
        for enode in self._edit_nodes:
            if enode["tformNode"] == name:
                return enode
        return None

    def active_image_index(self):
        for image in commands.renderedImages():
            value = _tag_value(image.tags, "tmanip_state")
            if value not in (None, ""):
                return image.index
        return -1

    def set_manip_state(self, pair, value):
        if pair is not None and commands.nodeExists(pair["tformNode"]):
            set_property(pair["tformNode"] + ".tag.tmanip_state", value)

    def control(self, index, event):
        corners = commands.imageGeometryByIndex(index)
        pointer = event.pointer()
        gc = _compute_gc(corners)

        for c in corners:
            vx = pointer[0] - c[0]
            vy = pointer[1] - c[1]
            if abs(vx) < 25 and abs(vy) < 25:
                if c[0] < gc[0]:
                    control = "TopLeftCorner" if c[1] > gc[1] else "BotLeftCorner"
                else:
                    control = "TopRightCorner" if c[1] > gc[1] else "BotRightCorner"
                return control, gc, c

        return "FreeTranslation", gc, gc

    def move(self, event):
        last = self._current_edit_node
        self._current_edit_node = None
        self._control = "NoControl"
        commands.setCursor(Qt.ArrowCursor)

        for pixel in commands.imagesAtPixel(event.pointer()):
            if not pixel.inside:
                continue

            tag = _tag_value(pixel.tags, "tmanip")
            if tag is None:
                continue

            self._current_edit_node = self._edit_node(tag)
            self.set_manip_state(self._current_edit_node, "hover")
            control, gc, corner = self.control(pixel.index, event)
            self._control = control
            self._gc = gc
            self._corner = corner

            cursor_map = {
                "TopRightCorner": Qt.SizeBDiagCursor,
                "BotLeftCorner": Qt.SizeBDiagCursor,
                "TopLeftCorner": Qt.SizeFDiagCursor,
                "BotRightCorner": Qt.SizeFDiagCursor,
                "FreeTranslation": Qt.OpenHandCursor,
            }
            commands.setCursor(cursor_map.get(self._control, Qt.WhatsThisCursor))
            break

        if last != self._current_edit_node:
            if last is not None:
                self.set_manip_state(last, "")
            commands.redraw()

        event.reject()

    def push(self, event):
        if self._current_edit_node is None:
            return

        commands.setCursor(Qt.ClosedHandCursor)
        self.set_manip_state(self._current_edit_node, "editing")

        if self.active_image_index() == -1:
            return

        self._down_point = event.pointer()
        self._did_drag = False
        self._editing = True
        commands.redraw()

    def drag(self, event):
        if self._current_edit_node is None:
            return

        index = self.active_image_index()
        commands.setCursor(Qt.ClosedHandCursor)
        if index == -1:
            return

        tform_node = self._current_edit_node["tformNode"]
        trans_prop = "%s.transform.translate" % tform_node
        scale_prop = "%s.transform.scale" % tform_node
        trans = commands.getFloatProperty(trans_prop)
        scale = commands.getFloatProperty(scale_prop)
        corners = commands.imageGeometryByIndex(index)
        a, b, _, d = corners[0], corners[1], corners[2], corners[3]
        pp = event.pointer()
        dp = self._down_point
        ip = (pp[0] - dp[0], pp[1] - dp[1])
        ba = _mag(a, b)
        da = _mag(d, a)
        aspect = ba / da if da else 1.0
        dx = ip[0] / ba * scale[0] * aspect if ba else 0.0
        dy = ip[1] / da * scale[1] if da else 0.0
        diag_dir = _normalize((self._corner[0] - self._gc[0], self._corner[1] - self._gc[1]))
        diag_dist = _dot((pp[0] - self._gc[0], pp[1] - self._gc[1]), diag_dir)
        down_dist = _dot((self._down_point[0] - self._gc[0], self._down_point[1] - self._gc[1]), diag_dir)
        diff = diag_dist - down_dist
        scl = (diag_dist - diff / 2.0) / down_dist if down_dist else 1.0
        sv = (diff * diag_dir[0], diff * diag_dir[1])
        sdx = sv[0] / ba * scale[0] * aspect if ba else 0.0
        sdy = sv[1] / da * scale[1] if da else 0.0

        if self._control == "FreeTranslation":
            set_property(trans_prop, [trans[0] + dx, trans[1] + dy])
        else:
            set_property(trans_prop, [trans[0] + sdx / 2.0, trans[1] + sdy / 2.0])
            new_scale = max(scale[0] * scl, 0.01)
            set_property(scale_prop, [new_scale, scale[1] * new_scale / scale[0]])

        self._down_point = pp
        self._did_drag = True
        commands.redraw()

    def release(self, _event):
        if self._editing:
            self.set_manip_state(self._current_edit_node, "hover")
            commands.setCursor(Qt.OpenHandCursor)
        else:
            commands.setCursor(Qt.ArrowCursor)

        self._did_drag = False
        self._editing = False

    def reset_all(self, _event):
        for enode in self._edit_nodes:
            tform_node = enode["tformNode"]
            set_property("%s.transform.translate" % tform_node, [0.0, 0.0])
            set_property("%s.transform.scale" % tform_node, [1.0, 1.0])
            set_property("%s.transform.rotate" % tform_node, [0.0])
        commands.redraw()

    def _node_aspect(self, node):
        geom = commands.nodeImageGeometry(commands.viewNode(), commands.frame())
        pa = geom.pixelAspect
        xps = pa if pa > 1.0 else 1.0
        yps = pa if pa < 1.0 else 1.0
        return (geom.width * xps) / (geom.height / yps)

    def fit_all(self, _event):
        aspect = self._node_aspect(commands.viewNode())
        for enode in self._edit_nodes:
            tform_node = enode["tformNode"]
            in_aspect = self._node_aspect(tform_node)
            s = aspect / in_aspect if in_aspect else 1.0
            set_property("%s.transform.translate" % tform_node, [0.0, 0.0])
            set_property("%s.transform.scale" % tform_node, [s, s])
            set_property("%s.transform.rotate" % tform_node, [0.0])
        commands.redraw()

    def remove_tags(self):
        for entry in self._edit_nodes:
            node = entry["tformNode"]
            for prop in (node + ".tag.tmanip", node + ".tag.tmanip_state"):
                if commands.propertyExists(prop):
                    commands.deleteProperty(prop)

    def find_editing_nodes(self, set_states=True):
        vnode = commands.viewNode()
        infos = commands.metaEvaluateClosestByType(commands.frame(), "RVTransform2D")
        ins = commands.nodeConnections(vnode, False)[0]

        self._edit_nodes = []
        if len(infos) != len(ins):
            return

        for i, info in enumerate(infos):
            node = info["node"] if isinstance(info, dict) else info.node
            pname = node + ".tag.tmanip"
            sname = node + ".tag.tmanip_state"
            self._edit_nodes.append({"tformNode": node, "inputNode": ins[i]})
            if set_states or not commands.propertyExists(pname):
                set_property(pname, node)
                set_property(sname, "")

    def node_inputs_changed(self, event):
        node = event.contents()
        vnode = commands.viewNode()
        if vnode is not None and node == vnode:
            self.find_editing_nodes(False)

    def after_graph_view_change(self, event):
        self.find_editing_nodes()
        event.reject()

    def graph_state_change(self, event):
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) >= 3 and parts[1] == "layout" and parts[2] == "mode":
            try:
                if commands.getStringProperty("#RVLayoutGroup.layout.mode")[0] == "manual":
                    self.find_editing_nodes()
            except Exception:
                pass
        event.reject()

    def before_graph_view_change(self, event):
        self.remove_tags()
        event.reject()

    def activate(self):
        self.find_editing_nodes()

    def deactivate(self):
        commands.setCursor(Qt.ArrowCursor)
        self.remove_tags()

    def _setup_projection(self, event):
        domain = event.domain()
        vflip = False
        if hasattr(event, "domainVerticalFlip"):
            try:
                vflip = event.domainVerticalFlip()
            except Exception:
                vflip = False

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        if vflip:
            gluOrtho2D(0.0, domain[0] - 1, domain[1] - 1, 0.0)
        else:
            gluOrtho2D(0.0, domain[0] - 1, 0.0, domain[1] - 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def _config_color(self, which, default):
        try:
            config = commands.data().config
            color = getattr(config, which)
            return (float(color[0]), float(color[1]), float(color[2]))
        except Exception:
            return default

    def _draw_corners(self, corners, mult, width):
        for i, c in enumerate(corners):
            i0 = 3 if i == 0 else i - 1
            i1 = (i + 1) % 4
            c0 = corners[i0]
            c1 = corners[i1]
            m0 = _mag(c0, c)
            m1 = _mag(c1, c)
            dir0 = _normalize((c0[0] - c[0], c0[1] - c[1]))
            dir1 = _normalize((c1[0] - c[0], c1[1] - c[1]))
            nmult = 0.0 if (m1 / 2.0 < mult or m0 / 2.0 < mult) else mult

            glBegin(GL_LINES)
            glVertex2f(c[0] + dir0[0] * nmult, c[1] + dir0[1] * nmult)
            glVertex2f(c[0] - dir0[0] * width, c[1] - dir0[1] * width)
            glVertex2f(c[0] + dir1[0] * nmult, c[1] + dir1[1] * nmult)
            glVertex2f(c[0] - dir1[0] * width, c[1] - dir1[1] * width)
            glEnd()

    def render(self, event):
        if self._current_edit_node is None:
            return

        index = self.active_image_index()
        if index == -1:
            return

        self._setup_projection(event)

        try:
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
            self._draw_corners(corners, 25, 0.0)
            glLineWidth(6.0)
            glColor4f(1.0, 1.0, 1.0, 0.5)
            self._draw_corners(corners, 25, 0.0)

            glLineWidth(1.5)
            bg = self._config_color("bg", (0.2, 0.2, 0.2))
            fg = self._config_color("fg", (1.0, 1.0, 1.0))

            glPushMatrix()
            glTranslatef(gc[0], gc[1], 0.0)
            glScalef(25.0, 25.0, 25.0)
            glColor4f(bg[0], bg[1], bg[2], 0.5)
            _draw_circle_fan(False)
            _draw_circle_fan(True)
            glPopMatrix()

            glPushMatrix()
            glTranslatef(gc[0], gc[1], 0.0)
            glScalef(25.0, 25.0, 25.0)
            glColor4f(fg[0], fg[1], fg[2], 1.0)
            _translate_icon_glyph(False)
            glColor4f(fg[0] * 0.5, fg[1] * 0.5, fg[2] * 0.5, 1.0)
            glLineWidth(1.0)
            _translate_icon_glyph(True)
            glPopMatrix()

            glDisable(GL_BLEND)
        except Exception:
            pass


def sync_editing_tags() -> None:
    """Set tag.tmanip* properties on layout manual transforms (Mu parity)."""
    if g_the_mode is not None:
        g_the_mode.find_editing_nodes()
        return
    tmp = TransformManip()
    tmp.find_editing_nodes()


def createMode():
    global g_the_mode
    g_the_mode = TransformManip()
    return g_the_mode


def theMode():
    return g_the_mode
