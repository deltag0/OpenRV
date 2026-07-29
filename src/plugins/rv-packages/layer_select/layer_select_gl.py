#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Pure-Python GL draw for LayerSelect (no package .mu files).

Text and rounded boxes use Mu ``gltext`` / ``glyph`` via ``runtime.eval`` so
pixels match the original Mu mode; QPainter does not land in the GL framebuffer.
"""

from __future__ import annotations

import re

import rv.commands as rvc
import rv.runtime as runtime

from OpenGL.GL import (
    GL_BLEND,
    GL_POINTS,
    GL_POINT_SMOOTH,
    GL_PROJECTION,
    GL_QUADS,
    GL_MODELVIEW,
    glBegin,
    glColor4f,
    glDisable,
    glEnable,
    glEnd,
    glLoadIdentity,
    glMatrixMode,
    glPointSize,
    glVertex2f,
)
from OpenGL.GLU import gluOrtho2D

_gltext_inited = False


# Mu ``globalConfig`` defaults from ``rvui.mu`` (-noPrefs goldens use these).
_DEFAULT_BEVEL_MARGIN = 20
_DEFAULT_INFO_TEXT_SIZE = 14
_DEFAULT_BG = (0.0, 0.0, 0.0)
_DEFAULT_FG = (0.75, 0.75, 0.75)

_config_cache: dict[str, int | tuple[float, float, float]] | None = None


def _refresh_config_cache() -> None:
    global _config_cache
    _config_cache = {
        "margin": _DEFAULT_BEVEL_MARGIN,
        "text_size": _DEFAULT_INFO_TEXT_SIZE,
        "bg": _DEFAULT_BG,
        "fg": _DEFAULT_FG,
    }


def ensure_config_loaded() -> None:
    if _config_cache is None:
        _refresh_config_cache()


def bevel_margin() -> int:
    ensure_config_loaded()
    return int(_config_cache["margin"])


def _config_color(which: str, default=(1.0, 1.0, 1.0)):
    if _config_cache is None:
        _refresh_config_cache()
    key = "bg" if which == "bg" else "fg" if which == "fg" else which
    if key in _config_cache:
        return _config_cache[key]  # type: ignore[return-value]
    return default


def _info_text_size() -> int:
    if _config_cache is None:
        _refresh_config_cache()
    return int(_config_cache["text_size"])


def _ensure_gltext() -> None:
    global _gltext_inited
    if _gltext_inited:
        return
    runtime.eval("{ use gltext; gltext.init(); }", ["gltext"])
    _gltext_inited = True


def _mu_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


_MU_MODULES = ["rvtypes", "glyph", "gltext", "gl"]


def _pairs_init_mu(pairs: list[tuple[str, str]]) -> str:
    lines = ["StringPair[] pairs;"]
    for name, val in pairs:
        lines.append('pairs.push_back(("%s", "%s"));' % (_mu_str(name), _mu_str(val)))
    return "\n".join(lines)


_MU_NAME_VALUE_BOUNDS_RE = re.compile(
    r"^\(<([^,]+),\s*([^>]+)>,.*,\s*([0-9.+-]+)\)$"
)


def _parse_name_value_bounds_result(result) -> tuple[float, float, float]:
    if isinstance(result, str):
        match = _MU_NAME_VALUE_BOUNDS_RE.match(result.strip())
        if match:
            return float(match.group(1)), float(match.group(2)), float(match.group(3))
    if isinstance(result, (list, tuple)) and len(result) >= 4:
        entry = result[0]
        if hasattr(entry, "x"):
            tbox_w, tbox_h = float(entry.x), float(entry.y)
        else:
            tbox_w, tbox_h = float(entry[0]), float(entry[1])
        return tbox_w, tbox_h, float(result[3])
    raise TypeError("unexpected nameValuePairBounds result: %r" % (result,))


def _mu_layout_and_draw(
    pairs: list[tuple[str, str]],
    fg: tuple[float, float, float],
    bg: tuple[float, float, float],
    x: int,
    y: int,
    margin: int,
    nobox: bool,
    text_size: int,
    close_hover: bool,
    close_x: float,
    close_y: float,
    close_r: float,
    need_bounds_only: bool,
) -> tuple[float, float, float, float, float]:
    """One Mu eval per call: bounds, optional draw, metrics (Mu render parity)."""
    _ensure_gltext()
    draw_block = ""
    if not need_bounds_only:
        draw_block = (
            "let r = drawNameValuePairs("
            "expandNameValuePairs(pairs), "
            "Color(%(fr)f, %(fg)f, %(fb)f, 1), Color(%(br)f, %(bg)f, %(bb)f, 0.75), "
            "%(x)d, %(y)d, %(m)d, 0, 0, 0, 0, %(nobox)s); "
            % {
                "fr": fg[0],
                "fg": fg[1],
                "fb": fg[2],
                "br": bg[0],
                "bg": bg[1],
                "bb": bg[2],
                "x": x,
                "y": y,
                "m": margin,
                "nobox": "true" if nobox else "false",
            }
        )
        draw_block += "let tb = r._0; let fd = gltext.descenderDepth(); let th = gltext.ascenderHeight() - fd; (tb[0], tb[1], r._3, fd, th);"
    else:
        draw_block = (
            "let b = nameValuePairBounds(expandNameValuePairs(pairs), %(m)d); "
            "let fd = gltext.descenderDepth(); let th = gltext.ascenderHeight() - fd; "
            "(b._0[0], b._0[1], b._3, fd, th);"
            % {"m": margin}
        )

    result = runtime.eval(
        (
            "{ use rvtypes; use glyph; use gltext; use gl; gltext.size(%(sz)d); %(pairs)s "
            + draw_block
            + " }"
        )
        % {"sz": text_size, "pairs": _pairs_init_mu(pairs)},
        _MU_MODULES,
    )
    if isinstance(result, str):
        # Tuple string: (w, h, nw, fd, th)
        m = re.match(r"^\(([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)$", result.strip())
        if m:
            return (
                float(m.group(1)),
                float(m.group(2)),
                float(m.group(3)),
                float(m.group(4)),
                float(m.group(5)),
            )
    if isinstance(result, (list, tuple)) and len(result) >= 5:
        return (
            float(result[0]),
            float(result[1]),
            float(result[2]),
            float(result[3]),
            float(result[4]),
        )
    raise TypeError("unexpected Mu layout result: %r" % (result,))


def _mu_draw_close(
    x: float,
    y: float,
    radius: float,
    bg: tuple[float, float, float],
    fg: tuple[float, float, float],
) -> None:
    runtime.eval(
        (
            "{ use rvtypes; use glyph; drawCloseButton(%(x)f, %(y)f, %(r)f, "
            "Color(%(br)f, %(bg)f, %(bb)f, 0.75), Color(%(fr)f, %(fg)f, %(fb)f, 1)); }"
        )
        % {
            "x": x,
            "y": y,
            "r": radius,
            "br": bg[0],
            "bg": bg[1],
            "bb": bg[2],
            "fr": fg[0],
            "fg": fg[1],
            "fb": fg[2],
        },
        ["rvtypes", "glyph"],
    )


def _setup_projection(event) -> None:
    domain = event.domain()
    vflip = event.domainVerticalFlip()
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    if vflip:
        gluOrtho2D(0.0, domain[0] - 1, domain[1] - 1, 0.0)
    else:
        gluOrtho2D(0.0, domain[0] - 1, 0.0, domain[1] - 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


def render_layer_widget(event) -> tuple | None:
    """Draw the layer list HUD. Returns layout tuple or None."""
    sinfo = list(rvc.sourcesRendered())
    if not sinfo:
        return None
    iname = sinfo[0].name if hasattr(sinfo[0], "name") else sinfo[0]["name"]
    node = sinfo[0].node if hasattr(sinfo[0], "node") else sinfo[0]["node"]
    media = rvc.sourceMedia(iname)
    if media is None:
        return None
    layers = list(media[1]) if media[1] is not None else []
    if not layers:
        return None

    docked = bool(rvc.readSettings("LayerSelect", "widgetIsDocked", True))
    select_index = int(rvc.readSettings("LayerSelect", "selectLayerIndex", 0))
    close_hover = bool(rvc.readSettings("LayerSelect", "inCloseArea", False))
    wx = float(rvc.readSettings("LayerSelect", "widgetX", 40.0))
    wy = float(rvc.readSettings("LayerSelect", "widgetY", 60.0))

    prop = "%s.request.imageComponent" % node
    active_layer = ""
    if rvc.propertyExists(prop):
        img_comp = list(rvc.getStringProperty(prop))
        if len(img_comp) == 3 and img_comp[0] == "layer":
            active_layer = img_comp[2]

    attrs: list[tuple[str, str]] = []
    active_indices: list[int] = []
    for i in range(len(layers) - 1, -1, -1):
        attrs.append(("        ", layers[i]))
        if active_layer == layers[i]:
            active_indices.append(i)
    if active_layer == "":
        active_indices.append(-1)
    attrs.append(("        ", "Default"))

    if _config_cache is None:
        _refresh_config_cache()
    _setup_projection(event)
    bg = _config_color("bg", (0.0, 0.0, 0.0))
    fg = _config_color("fg", (0.75, 0.75, 0.75))
    margin = bevel_margin()
    text_size = _info_text_size()
    x = 0 if docked else int(wx + margin)
    v_margins = list(rvc.margins())
    vs = rvc.viewSize()

    tbox_w, tbox_h, nw, fd, th = _mu_layout_and_draw(
        attrs,
        fg,
        bg,
        x,
        0,
        margin,
        docked,
        text_size,
        False,
        0.0,
        0.0,
        0.0,
        True,
    )

    yspace = vs[1] - v_margins[3] - v_margins[2]
    midy = v_margins[3] + yspace / 2.0
    adjy = midy - tbox_h / 2.0
    target_y = max(v_margins[3] + margin, adjy + margin)
    target_w = tbox_w + 1.25 * margin
    widget_y = wy

    if docked:
        widget_y = target_y - margin
        w = max(v_margins[0], target_w)
        glColor4f(0.0, 0.0, 0.0, 1.0)
        glBegin(GL_QUADS)
        glVertex2f(0.0, vs[1] - v_margins[2])
        glVertex2f(w, vs[1] - v_margins[2])
        glVertex2f(w, v_margins[3])
        glVertex2f(0.0, v_margins[3])
        glEnd()

    y = int(widget_y + margin)
    emin = (0.0 if docked else wx, widget_y)
    emax = (
        emin[0] + tbox_w + margin + (margin / 4.0 if docked else margin),
        emin[1] + tbox_h + margin,
    )

    close_x = x - margin / 2.0
    close_y = tbox_h + y - margin - margin / 4.0
    close_r = margin / 2.0
    tbox_w, tbox_h, nw, fd, th = _mu_layout_and_draw(
        attrs,
        fg,
        bg,
        x,
        y,
        margin,
        docked,
        text_size,
        False,
        0.0,
        0.0,
        0.0,
        False,
    )

    gx = x + margin / 2.0
    glEnable(GL_POINT_SMOOTH)
    glPointSize(6.0)
    glBegin(GL_POINTS)
    glColor4f(0.75, 0.75, 0.15, 1.0)
    gy = y + th * (len(layers) - select_index) + fd + th / 2.0 + 2.0
    glVertex2f(gx, gy)
    glColor4f(0.15, 0.75, 0.75, 1.0)
    for ai in active_indices:
        agy = y + th * (len(layers) - ai - 1) + fd + th / 2.0 + 2.0
        glVertex2f(gx, agy)
    glEnd()

    if close_hover:
        _mu_draw_close(close_x, close_y, close_r, bg, fg)

    glDisable(GL_BLEND)
    glDisable(GL_POINT_SMOOTH)

    return (float(tbox_w), float(tbox_h), float(th), float(nw), emin, emax, float(widget_y))
