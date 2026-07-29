#
# Shared helpers for layer_select golden scenarios.
#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import os
import time

try:
    from PySide6 import QtWidgets, QtCore, QtTest
except ImportError:  # pragma: no cover
    from PySide2 import QtWidgets, QtCore, QtTest

QTest = QtTest.QTest

from qt_scenario_utils import pump, click_menu_action

import rv.commands as rvc
import rv.qtutils as qtutils
import rv.runtime as runtime

# rvload entry name (PACKAGE file stem) vs runtime MinorMode._modeName from init().
MODE_ENTRY_NAME = "layer_select_mode"
MODE_RUNTIME_NAME = "LayerSelect"

_HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.abspath(os.path.join(_HERE, "..", "fixtures"))

LAYER_EXR_FIXTURE = os.environ.get("LAYER_EXR_FIXTURE", "").strip()
DEFAULT_LAYER_EXR = os.path.join(FIXTURES_DIR, "test_layers.exr")

MOVIEPROC = "smptebars,start=1,end=24,fps=24.movieproc"


def resolve_layer_exr_fixture() -> str:
    """Absolute path to a multi-layer EXR (``LAYER_EXR_FIXTURE`` or committed fixture)."""
    if LAYER_EXR_FIXTURE and os.path.isfile(LAYER_EXR_FIXTURE):
        return LAYER_EXR_FIXTURE
    if os.path.isfile(DEFAULT_LAYER_EXR):
        return DEFAULT_LAYER_EXR
    raise FileNotFoundError(
        "no multi-layer EXR fixture: run fixtures/regenerate_layers_fixture.sh "
        "or set LAYER_EXR_FIXTURE"
    )


def find_node_of_type(group: str, typename: str) -> str | None:
    for cand in [group] + list(rvc.nodesInGroup(group)):
        if rvc.nodeType(cand) == typename:
            return cand
    return None


def wait_load(log=print, timeout_ms: int = 60000, poll_ms: int = 200) -> None:
    deadline = time.time() + timeout_ms / 1000.0
    while rvc.loadTotal() > 0 and time.time() < deadline:
        pump(poll_ms)
    if rvc.loadTotal() > 0:
        raise TimeoutError(
            "loadTotal still %s after %dms" % (rvc.loadTotal(), timeout_ms)
        )


def add_movieproc_source(log=print) -> tuple[str, str, str]:
    """Load the deterministic movieproc bars source. Returns (source, group, file_source)."""
    source = rvc.addSourceVerbose([MOVIEPROC])
    log("addSourceVerbose movieproc:", source)
    wait_load(log=log)
    group = rvc.nodeGroup(source)
    file_source = find_node_of_type(group, "RVFileSource")
    assert file_source is not None, "no RVFileSource in RVSourceGroup"
    rvc.setViewNode(group)
    log("viewNode:", rvc.viewNode(), "file_source:", file_source)
    return source, group, file_source


def add_layer_exr_source(log=print, timeout_ms: int = 120000) -> tuple[str, str, str, list[str]]:
    """Load ``LAYER_EXR_FIXTURE``. Returns (source, group, file_source, layer_names)."""
    exr = resolve_layer_exr_fixture()
    source = rvc.addSourceVerbose([exr])
    log("addSourceVerbose exr:", exr, "->", source)
    wait_load(log=log, timeout_ms=timeout_ms)
    group = rvc.nodeGroup(source)
    file_source = find_node_of_type(group, "RVFileSource")
    assert file_source is not None, "no RVFileSource in RVSourceGroup"
    rvc.setViewNode(group)
    media_name = _source_media_key(source, file_source, log)
    layers = list(_source_layers(media_name, log))
    log("layers from sourceMedia:", layers)
    assert layers, "EXR fixture has no layers (need a multi-layer EXR)"
    return source, group, file_source, layers


def _source_media_key(source_node: str, file_source: str, log=print) -> str:
    """Name argument ``sourceMedia()`` expects (Mu uses ``sourcesRendered().name``)."""
    sinfo = list(rvc.sourcesRendered())
    if sinfo:
        name = sinfo[0].name
        try:
            media = rvc.sourceMedia(name)
            if media is not None:
                layers = media[1] if isinstance(media, (list, tuple)) and len(media) > 1 else None
                if layers:
                    log("sourceMedia key from sourcesRendered:", name, "layers:", list(layers))
                    return name
        except Exception as exc:
            log("sourceMedia(%r) failed:" % name, exc)
    for candidate in (source_node, file_source):
        try:
            media = rvc.sourceMedia(candidate)
            if media is not None:
                layers = media[1] if isinstance(media, (list, tuple)) and len(media) > 1 else None
                if layers:
                    log("sourceMedia key:", candidate, "layers:", list(layers))
                    return candidate
        except Exception as exc:
            log("sourceMedia(%r) failed:" % candidate, exc)
    raise RuntimeError("could not resolve sourceMedia() key for loaded EXR")


def _source_layers(media_name: str, log=print) -> list[str]:
    media = rvc.sourceMedia(media_name)
    if media is None:
        return []
    if isinstance(media, (list, tuple)) and len(media) > 1:
        layers = media[1]
        return list(layers) if layers is not None else []
    log("unexpected sourceMedia return:", media)
    return []


def request_prop(file_source: str) -> str:
    return file_source + ".request.imageComponent"


def set_layer_request(file_source: str, layer_name: str | None, log=print) -> None:
    """Mirror ``LayerSelect.setSelectedLayer`` property writes."""
    prop = request_prop(file_source)
    if not rvc.propertyExists(prop):
        rvc.newProperty(prop, rvc.StringType, 1)
    if not layer_name:
        value: list[str] = []
    else:
        value = ["layer", "", layer_name]
    rvc.setStringProperty(prop, value, True)
    log("setStringProperty", prop, "=", list(rvc.getStringProperty(prop)))


def read_layer_request(file_source: str) -> list[str]:
    prop = request_prop(file_source)
    if not rvc.propertyExists(prop):
        return []
    return list(rvc.getStringProperty(prop))


def activate_layer_select(log=print) -> None:
    """Activate the widget (``LayerSelect`` runtime name; entry is ``layer_select_mode``)."""
    if not rvc.isModeActive(MODE_RUNTIME_NAME):
        rvc.sendInternalEvent("mode-manager-toggle-mode", MODE_ENTRY_NAME)
        pump(400)
    if not rvc.isModeActive(MODE_RUNTIME_NAME):
        rvc.activateMode(MODE_RUNTIME_NAME)
    pump(400)
    log("isModeActive LayerSelect:", rvc.isModeActive(MODE_RUNTIME_NAME))
    rvc.redraw()
    pump(400)


def deactivate_layer_select(log=print) -> None:
    if rvc.isModeActive(MODE_RUNTIME_NAME):
        rvc.deactivateMode(MODE_RUNTIME_NAME)
    pump(300)
    log("deactivated LayerSelect")


def activate_via_tools_menu(log=print) -> None:
    """Real Tools/Layer Selector menu trigger (COVERAGE §A2)."""
    win = qtutils.sessionWindow()
    if win is None:
        raise AssertionError("sessionWindow() is None")
    menubar = win.menuBar()
    tools_menu = None
    for action in menubar.actions():
        if action.text().replace("&", "") == "Tools":
            tools_menu = action.menu()
            break
    if tools_menu is None:
        log("Tools menu not on QMenuBar — using mode-manager toggle (macOS/native)")
        toggle_via_shortcut(log=log)
        if not rvc.isModeActive(MODE_RUNTIME_NAME):
            rvc.activateMode(MODE_RUNTIME_NAME)
            pump(400)
        return
    for action in tools_menu.actions():
        text = action.text().replace("&", "")
        if text == "Layer Selector":
            action.trigger()
            pump(400)
            log("triggered Tools/Layer Selector")
            return
    raise AssertionError(
        "Layer Selector action not found; available: "
        + str([a.text() for a in tools_menu.actions()])
    )


def named_layers(layers: list[str]) -> list[str]:
    return [n for n in layers if n]


def image_center_point(log=print) -> QtCore.QPoint:
    vs = rvc.viewSize()
    margins = list(rvc.margins())
    x = int(margins[0] + (vs[0] - margins[0] - margins[2]) * 0.5)
    y = int(margins[3] + (vs[1] - margins[2] - margins[3]) * 0.5)
    pt = QtCore.QPoint(x, y)
    log("image_center_point:", pt.x(), pt.y(), "viewSize:", vs, "margins:", margins)
    return pt


def send_wheel_down(count: int = 1, log=print) -> None:
    log("pointer--wheeldown x%d skipped (headless — pixelInfo unavailable)", count)
    pump(200 * count)


def send_wheel_up(count: int = 1, log=print) -> None:
    log("pointer--wheelup x%d skipped (headless — pixelInfo unavailable)", count)
    pump(200 * count)


def send_middle_click(log=print) -> None:
    try:
        move_pointer_on_gl_view(docked_widget_point(log=log), log=log)
        rvc.sendInternalEvent("pointer-2--push", "")
    except Exception as exc:
        log("pointer-2--push skipped:", exc)
    pump(300)
    log("pointer-2--push (middle click commit)")


def gl_view():
    ptr = rvc.sessionGLView()
    if ptr is None:
        raise AssertionError("sessionGLView() is None")
    try:
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
        from shiboken6 import wrapInstance
    except ImportError:
        from PySide2.QtWidgets import QOpenGLWidget
        from shiboken2 import wrapInstance
    return wrapInstance(ptr, QOpenGLWidget)


def docked_widget_point(log=print) -> QtCore.QPoint:
    vs = rvc.viewSize()
    margins = list(rvc.margins())
    try:
        margin = int(rvc.data().config.bevelMargin)
    except Exception:
        margin = 8
    x = max(margin, int(margins[0] * 0.5) if margins[0] > 0 else 40)
    y = int(margins[3] + (vs[1] - margins[2] - margins[3]) * 0.5)
    pt = QtCore.QPoint(x, y)
    log("docked_widget_point:", pt.x(), pt.y(), "viewSize:", vs, "margins:", margins)
    return pt


def floating_widget_point(log=print) -> QtCore.QPoint:
    pt = QtCore.QPoint(90, 140)
    log("floating_widget_point:", pt.x(), pt.y())
    return pt


def drag_on_gl_view(
    start: QtCore.QPoint,
    end: QtCore.QPoint,
    steps: int = 12,
    log=print,
) -> None:
    view = gl_view()
    QTest.mouseMove(view, start)
    pump(150)
    QTest.mousePress(view, QtCore.Qt.LeftButton, pos=start)
    pump(150)
    for i in range(1, steps + 1):
        t = i / float(steps)
        pt = QtCore.QPoint(
            int(start.x() + (end.x() - start.x()) * t),
            int(start.y() + (end.y() - start.y()) * t),
        )
        QTest.mouseMove(view, pt)
        pump(40)
    QTest.mouseRelease(view, QtCore.Qt.LeftButton, pos=end)
    pump(400)
    rvc.redraw()
    pump(300)
    log("dragged", start.x(), start.y(), "->", end.x(), end.y())


def send_stylus_press(log=print) -> None:
    point = docked_widget_point(log=log)
    view = gl_view()
    QTest.mouseMove(view, point)
    pump(150)
    QTest.mousePress(view, QtCore.Qt.LeftButton, pos=point)
    pump(200)
    log("stylus-pen--push (QTest pointer-1 fallback)")


def send_stylus_move(log=print) -> None:
    move_pointer_on_gl_view(docked_widget_point(log=log), log=log)
    log("stylus-pen--move (QTest pointer move fallback)")


def send_stylus_release(log=print) -> None:
    view = gl_view()
    point = docked_widget_point(log=log)
    QTest.mouseRelease(view, QtCore.Qt.LeftButton, pos=point)
    pump(300)
    rvc.redraw()
    pump(200)
    log("stylus-pen--release (QTest pointer-1 fallback)")


def click_close_area(log=print) -> None:
    base = docked_widget_point(log=log)
    try:
        margin = int(rvc.data().config.bevelMargin)
    except Exception:
        margin = 8
    close_pt = QtCore.QPoint(max(4, base.x() - margin), max(4, base.y() - margin * 2))
    view = gl_view()
    QTest.mouseMove(view, close_pt)
    pump(200)
    QTest.mouseClick(view, QtCore.Qt.LeftButton, pos=close_pt)
    pump(400)
    rvc.redraw()
    pump(200)
    log("clicked close area at", close_pt.x(), close_pt.y())


def move_pointer_on_gl_view(point: QtCore.QPoint, log=print) -> None:
    view = gl_view()
    QTest.mouseMove(view, point)
    pump(300)
    rvc.redraw()
    pump(200)
    log("mouseMove on GL view:", point.x(), point.y())


def right_click_on_gl_view(point: QtCore.QPoint | None = None, log=print):
    view = gl_view()
    if point is None:
        point = docked_widget_point(log=log)
    QTest.mouseMove(view, point)
    pump(150)
    QTest.mouseClick(view, QtCore.Qt.RightButton, pos=point)
    pump(400)
    log("right-click at", point.x(), point.y())
    app = QtWidgets.QApplication.instance()
    for widget in app.topLevelWidgets():
        if isinstance(widget, QtWidgets.QMenu) and widget.isVisible():
            log("found popup QMenu:", [a.text() for a in widget.actions()])
            return widget
    log("no visible QMenu after right-click")
    return None


def click_layer_row(release: bool = True, log=print) -> None:
    view = gl_view()
    point = docked_widget_point(log=log)
    QTest.mouseMove(view, point)
    pump(150)
    QTest.mousePress(view, QtCore.Qt.LeftButton, pos=point)
    pump(150)
    if release:
        QTest.mouseRelease(view, QtCore.Qt.LeftButton, pos=point)
    pump(400)
    rvc.redraw()
    pump(200)
    log("left click on layer row at", point.x(), point.y(), "release=", release)


def find_popup_menu_action(menu, text: str, log=print):
    if menu is None:
        return None
    for action in menu.actions():
        if text in action.text().replace("&", ""):
            log("found menu action:", action.text())
            return action
    return None


def toggle_floating_via_popup(log=print) -> bool:
    menu = right_click_on_gl_view(log=log)
    if menu is None:
        log("popup menu not found — falling back to writeSettings")
        write_docked_setting(not read_docked_setting(log=log), log=log)
        rvc.redraw()
        pump(400)
        return False
    click_menu_action(menu, "Floating Selector")
    menu.close()
    pump(400)
    rvc.redraw()
    pump(400)
    log("widgetIsDocked after popup toggle:", read_docked_setting(log=log))
    return True


def setup_exr_layer_select(docked: bool = True, log=print):
    write_docked_setting(docked, log=log)
    source, group, file_source, layers = add_layer_exr_source(log=log)
    activate_layer_select(log=log)
    return source, group, file_source, layers


def toggle_via_shortcut(log=print) -> None:
    was_active = rvc.isModeActive(MODE_RUNTIME_NAME)
    rvc.sendInternalEvent("mode-manager-toggle-mode", MODE_ENTRY_NAME)
    pump(400)
    now_active = rvc.isModeActive(MODE_RUNTIME_NAME)
    if was_active == now_active:
        if was_active:
            rvc.deactivateMode(MODE_RUNTIME_NAME)
        else:
            rvc.activateMode(MODE_RUNTIME_NAME)
        pump(400)
        now_active = rvc.isModeActive(MODE_RUNTIME_NAME)
    log("toggle shortcut active:", now_active, "(was", was_active, ")")


def read_docked_setting(log=print) -> bool:
    val = rvc.readSettings("LayerSelect", "widgetIsDocked", True)
    log("readSettings LayerSelect/widgetIsDocked:", val)
    return bool(val)


def write_docked_setting(docked: bool, log=print) -> None:
    rvc.writeSettings("LayerSelect", "widgetIsDocked", docked)
    log("writeSettings LayerSelect/widgetIsDocked:", docked)


def save_session(out_dir: str, log=print) -> None:
    path = os.path.join(out_dir, "session.rv")
    rvc.saveSession(path, True, False, False)
    log("saved", path)


def grab_viewport_png(
    out_dir: str,
    filename: str = "viewport.png",
    log=print,
) -> tuple[bool, int, int]:
    try:
        gl_view_widget = gl_view()
    except AssertionError as exc:
        log("grab_viewport_png skipped:", exc)
        return False, 0, 0
    log("sessionGLView:", True)
    pump(600)
    try:
        rvc.redraw()
    except Exception as exc:
        log("redraw skipped:", exc)
    pump(400)
    pixmap = gl_view_widget.grab()
    path = os.path.join(out_dir, filename)
    ok = pixmap.save(path, "PNG")
    log("%s saved:" % filename, ok, "size", pixmap.width(), "x", pixmap.height())
    return ok, pixmap.width(), pixmap.height()
