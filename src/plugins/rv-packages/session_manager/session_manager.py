#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Python port of the RV ``session_manager`` package (Mu -> Python migration)."""

from __future__ import annotations

import os
import sys

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QFile, QModelIndex, QPoint, QSize, QTimer
    from PySide6.QtGui import QBrush, QColor, QIcon, QPixmap, QStandardItem, QStandardItemModel
    from PySide6.QtUiTools import QUiLoader
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QDockWidget,
        QHBoxLayout,
        QLabel,
        QTreeView,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover - Qt5 builds
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt, QFile, QModelIndex, QPoint, QSize, QTimer, QVariant
    from PySide2.QtGui import QBrush, QColor, QIcon, QPixmap, QStandardItem, QStandardItemModel
    from PySide2.QtUiTools import QUiLoader
    from PySide2.QtWidgets import (
        QAbstractItemView,
        QDockWidget,
        QHBoxLayout,
        QLabel,
        QTreeView,
        QVBoxLayout,
        QWidget,
    )

from rv import commands, extra_commands, qtutils, rvtypes

import session_manager as _sm_module

from session_manager_interactions import InputsView, SessionManagerInteractions
from session_manager_support import (
    ChannelSubComponent,
    LayerSubComponent,
    MediaSubComponent,
    NotASubComponent,
    ViewSubComponent,
    USER_ROLE_HASH,
    USER_ROLE_MEDIA,
    USER_ROLE_NODE,
    USER_ROLE_PARENT,
    USER_ROLE_SORT,
    USER_ROLE_SUBTYPE,
    USER_ROLE_SUBVALUE,
    hashed_sub_component_item,
    is_sub_component_expanded,
    item_is_sub_component,
    item_node,
    item_sub_component_type,
    item_sub_component_type_for_name,
    item_sub_component_value,
    set_property,
    set_sub_component_expanded,
    set_tool_tip_prop,
    source_node_of_group,
    sub_component_prop_value,
)
from session_manager_tree import NodeModel, NodeTreeView

MODE_NAME = "session_manager"

SOURCE_PREVIEW_WIDTH = 80
SOURCE_PREVIEW_HEIGHT = 45
SOURCE_ROW_HEIGHT = 55
SOURCE_ROW_MARGIN = 8
SOURCE_ROW_SPACING = 5
SOURCE_TEXT_SPACING = 3
TREE_VIEW_INDENTATION = 10
INT_MAX = 2147483647
FILMSTRIP_FRAME_WIDTH = 240
WIDE_PANEL_WIDTH = 371
NARROW_PANEL_WIDTH = 319

g_the_mode = None


def setToolTipProp(node: str, tool_tip: str) -> None:
    set_tool_tip_prop(node, tool_tip)


def sessionManagerReady() -> bool:
    return theMode() is not None


def selectedNodesExport() -> str:
    mode = theMode()
    if mode is None:
        return ""
    return "\n".join(mode.selectedNodes())


def _aux_file_path(mode, name: str) -> str:
    return os.path.join(mode.supportPath(_sm_module, "session_manager"), name)


def _aux_icon(name: str, color_adjust: bool = False) -> QIcon:
    # color_adjust matches Mu dark-UI path; icons resolve from global :images/ qrc.
    del color_adjust
    return QIcon(":images/" + name)


def _set_property(prop_name: str, value) -> None:
    set_property(prop_name, value)


def _item_node(item: QStandardItem | None) -> str:
    return item_node(item)


def _item_is_sub_component(item: QStandardItem) -> bool:
    return item_is_sub_component(item)


def _contains(values: list[str], value: str) -> bool:
    return value in values


def _remove(values: list[str], value: str) -> list[str]:
    return [v for v in values if v != value]


def _index_of(values: list[str], value: str) -> int:
    try:
        return values.index(value)
    except ValueError:
        return -1


def _is_expanded_in_parent(node: str, parent: str) -> bool:
    prop_name = "%s.sm_state.expandState" % node
    if commands.propertyExists(prop_name):
        return _contains(commands.getStringProperty(prop_name), parent)
    return False


def _set_expanded_in_parent(node: str, parent: str, expanded: bool) -> None:
    prop_name = "%s.sm_state.expandState" % node
    if commands.propertyExists(prop_name):
        props = list(commands.getStringProperty(prop_name))
        has_node = _contains(props, parent)
        if has_node and not expanded:
            _set_property(prop_name, _remove(props, parent))
        elif not has_node and expanded:
            props.append(parent)
            _set_property(prop_name, props)
    elif expanded:
        _set_property(prop_name, parent)


def _sort_key_in_parent(node: str, parent: str) -> int:
    prop_parent = "%s.sm_state.sortKeyParent" % node
    prop_key = "%s.sm_state.sortKey" % node
    undefined = sys.maxsize - 100
    if commands.propertyExists(prop_parent) and commands.propertyExists(prop_key):
        try:
            parents = commands.getStringProperty(prop_parent)
            keys = commands.getIntProperty(prop_key)
            idx = _index_of(parents, parent)
            if idx == -1 or len(keys) != len(parents):
                return undefined
            return keys[idx]
        except Exception:
            pass
    return undefined


def _tool_tip_from_prop(node: str) -> str | None:
    prop_name = "%s.sm_state.toolTip" % node
    if commands.propertyExists(prop_name):
        try:
            return commands.getStringProperty(prop_name)[0]
        except Exception:
            pass
    return None


def _add_row(parent_item: QStandardItem, children: list[QStandardItem]) -> None:
    row = parent_item.rowCount()
    for col, child in enumerate(children):
        parent_item.setChild(row, col, child)


def _resize_columns(tree_view: QTreeView, model: QStandardItemModel) -> None:
    for col in range(model.columnCount(QModelIndex())):
        tree_view.resizeColumnToContents(col)


def _node_from_index(index: QModelIndex, model: QStandardItemModel) -> str:
    return _item_node(model.itemFromIndex(index))


class ThumbnailWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fallback = QPixmap()
        self.setScaledContents(True)

    def setFallback(self, pixmap: QPixmap) -> None:
        self._fallback = pixmap
        self.setPixmap(pixmap)

    def load(self, image: QtGui.QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        if not pixmap.isNull():
            self.setPixmap(pixmap)


class FilmstripWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._strip = QtGui.QImage()
        self._frame_width = FILMSTRIP_FRAME_WIDTH
        self._loaded = False
        self.setScaledContents(True)
        self.setMouseTracking(True)

    def isLoaded(self) -> bool:
        return self._loaded

    def load(self, filmstrip_image: QtGui.QImage) -> None:
        if not filmstrip_image.isNull():
            self._strip = filmstrip_image
            self._loaded = True

    def showFrameAtX(self, mouse_x: int) -> None:
        if not self._loaded or self.width() <= 0:
            return
        native_width = self._strip.width()
        proportion = float(mouse_x) / float(self.width())
        frame_x = int(proportion * float(native_width) / float(self._frame_width) + 0.5)
        frame_x *= self._frame_width
        frame_x = max(0, min(frame_x, native_width - self._frame_width))
        frame = self._strip.copy(
            QtCore.QRect(frame_x, 0, self._frame_width, self._strip.height())
        )
        self.setPixmap(QPixmap.fromImage(frame))

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        self.showFrameAtX(pos.x())
        super().mouseMoveEvent(event)


class SourcePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._thumbnail = ThumbnailWidget(self)
        self._filmstrip = FilmstripWidget(self)
        layout.addWidget(self._thumbnail)
        layout.addWidget(self._filmstrip)
        self._filmstrip.hide()

    def setFallback(self, pixmap: QPixmap) -> None:
        self._thumbnail.setFallback(pixmap)

    def loadThumbnail(self, image: QtGui.QImage) -> None:
        self._thumbnail.load(image)

    def loadStrip(self, image: QtGui.QImage) -> None:
        self._filmstrip.load(image)
        if self._filmstrip.isLoaded():
            self._filmstrip.show()
            self._filmstrip.showFrameAtX(0)


class SessionManagerMode(SessionManagerInteractions, rvtypes.MinorMode):
    """Session Manager dock panel and node tree."""

    def __init__(self):
        rvtypes.MinorMode.__init__(self)
        self._dark_ui = True
        self._input_order_lock = False
        self._quitting = False
        self._disable_updates = False
        self._progressive_loading_in_progress = commands.loadTotal() != 0
        self._previews_enabled = True
        previews_env = os.getenv("RV_SESSION_MANAGER_USE_THUMBNAILS")
        if previews_env is not None and previews_env == "0":
            self._previews_enabled = False
        else:
            try:
                self._previews_enabled = bool(
                    commands.readSettings("SessionManager", "previewsEnabled", True)
                )
            except Exception:
                pass
        self._previews_cache: list[tuple[str, QtGui.QImage]] = []

        self._dock_widget = None
        self._base_widget = None
        self._view_tree_view = None
        self._view_model = None
        self._inputs_model = None
        self._inputs_view = None
        self._tab_widget = None
        self._view_label = None
        self._prev_view_button = None
        self._next_view_button = None
        self._lazy_update_timer = None
        self._type_icons: list[tuple[str, QIcon]] = []
        self._view_icon = None
        self._unknown_type_icon = None
        self._fallback_source_icon = None
        self._editors = []
        self._ui_tree_widget = None
        self._building_panel = False
        self._src_node_keys: list[str] = []
        self._grp_node_values: list[str] = []

        self._init_interaction_state()

        self.init(
            MODE_NAME,
            [
                ("new-node", self._update_tree_event, "New user node"),
                ("source-modified", self._update_tree_event, "New source media"),
                ("source-group-complete", self._on_source_group_complete, "Source group complete"),
                ("before-progressive-loading", self._before_progressive_loading, "before loading"),
                ("after-progressive-loading", self._after_progressive_loading, "after loading"),
                ("after-node-delete", self._update_tree_event, "Node deleted"),
                ("after-clear-session", self._after_clear_session, "Session Cleared"),
                ("after-graph-view-change", self._after_graph_view_change, "Update session UI"),
                ("before-graph-view-change", self._before_graph_view_change, "Update session UI"),
                ("graph-node-inputs-changed", self._node_inputs_changed, "Update session UI"),
                ("graph-state-change", self._property_changed, "Maybe update session UI"),
                ("before-session-deletion", self._enter_quitting_state, "Store quitting before session goes away"),
                ("view-edit-mode-activated", self._view_edit_mode_activated, "Per-view edit mode activated, load UI"),
                ("event-category-state-changed", self._on_category_state_changed, "Category state changed"),
                ("session-manager-preview-available", self._update_node_preview_event, "Update preview widget"),
            ],
            None,
        )
        self._ignore_tab_save = False

    def toggle(self) -> None:
        """Match Mu MinorMode.toggle; keep dock visibility in sync."""
        if self._active:
            self.deactivate()
            commands.deactivateMode(MODE_NAME)
        else:
            self._active = True
            commands.activateMode(MODE_NAME)
            self.activate()
        commands.redraw()
        try:
            commands.writeSettings("Tools", "show_session_manager", self._active)
        except Exception:
            pass
        commands.sendInternalEvent("mode-toggled", "%s|%s" % (MODE_NAME, self._active), "Mode")

    def _attach_dock(self) -> None:
        if self._dock_widget is None:
            return
        main_window = qtutils.sessionWindow()
        if main_window is None:
            return
        try:
            from PySide6.QtCore import Qt
        except ImportError:  # pragma: no cover
            from PySide2.QtCore import Qt
        if main_window.dockWidgetArea(self._dock_widget) == Qt.DockWidgetArea.NoDockWidgetArea:
            main_window.addDockWidget(Qt.LeftDockWidgetArea, self._dock_widget)

    def _build_panel(self) -> None:
        main_window = qtutils.sessionWindow()
        if main_window is None:
            print("session_manager: main window not ready — deferring panel build")
            return
        support_dir = self.supportPath(_sm_module, "session_manager")

        self._dock_widget = QDockWidget("Session Manager", main_window)
        loader = QUiLoader()
        ui_path = os.path.join(support_dir, "session_manager.ui")
        if not os.path.isfile(ui_path):
            ui_path = os.path.join(os.path.dirname(_sm_module.__file__), "session_manager.ui")
        ui_file = QFile(ui_path)
        if not ui_file.open(QFile.ReadOnly):
            print("session_manager: failed to open UI file %s" % ui_path)
            return
        # Parent to the main window like Mu; setWidget() reparents into the dock.
        self._base_widget = loader.load(ui_file, main_window)
        ui_file.close()
        if self._base_widget is None:
            print("session_manager: QUiLoader failed for %s" % ui_path)
            return

        tree_view_base = self._base_widget.findChild(QWidget, "treeView")
        inputs_view_base = self._base_widget.findChild(QWidget, "inputsListView")
        if tree_view_base is None or inputs_view_base is None:
            print(
                "session_manager: UI missing treeView or inputsListView in %s"
                % ui_path
            )
            return
        self._tab_widget = self._base_widget.findChild(QtWidgets.QTabWidget, "tabWidget")
        self._view_label = self._base_widget.findChild(QLabel, "viewLabel")
        self._prev_view_button = self._base_widget.findChild(QtWidgets.QToolButton, "prevViewButton")
        self._next_view_button = self._base_widget.findChild(QtWidgets.QToolButton, "nextViewButton")
        self._ui_tree_widget = self._base_widget.findChild(QtWidgets.QTreeWidget, "uiTreeWidget")

        self._lazy_update_timer = QTimer(self._dock_widget)
        self._lazy_update_timer.setSingleShot(True)
        self._lazy_update_timer.timeout.connect(self.update_tree)

        vbox = QVBoxLayout(tree_view_base)
        vbox.setContentsMargins(0, 0, 0, 0)
        self._view_tree_view = NodeTreeView(tree_view_base)
        vbox.addWidget(self._view_tree_view)

        ivbox = QVBoxLayout(inputs_view_base)
        ivbox.setContentsMargins(0, 0, 0, 0)
        self._inputs_view = InputsView(self._view_tree_view, inputs_view_base, self.update_tree)
        ivbox.addWidget(self._inputs_view)
        self._inputs_view.setObjectName("inputsViewList")

        self._dock_widget.setWidget(self._base_widget)
        nav_panel = self._base_widget.findChild(QWidget, "navPanel")
        if nav_panel is not None:
            self._dock_widget.setTitleBarWidget(nav_panel)
            # navPanel leaves _baseWidget's tree; refresh refs from the reparented widget.
            self._view_label = nav_panel.findChild(QLabel, "viewLabel")
            self._prev_view_button = nav_panel.findChild(QtWidgets.QToolButton, "prevViewButton")
            self._next_view_button = nav_panel.findChild(QtWidgets.QToolButton, "nextViewButton")
        self._dock_widget.setObjectName(MODE_NAME)

        self._view_model = NodeModel(main_window)
        self._inputs_model = QStandardItemModel(main_window)
        self._view_tree_view._view_model = self._view_model
        self._view_model.setHorizontalHeaderLabels(["Name", "*", "*"])
        self._view_tree_view.header().setMinimumSectionSize(-1)
        self._view_tree_view.setModel(self._view_model)
        self._view_tree_view.setDragEnabled(True)
        self._view_tree_view.setAcceptDrops(True)
        if hasattr(self._view_tree_view, "setShowDropIndicator"):
            self._view_tree_view.setShowDropIndicator(True)
        self._view_tree_view.setHeaderHidden(False)
        self._view_tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._view_tree_view.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self._view_tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view_tree_view.setDragDropMode(QAbstractItemView.DragDrop)
        self._view_tree_view.setDefaultDropAction(Qt.MoveAction)
        self._view_tree_view.setExpandsOnDoubleClick(False)
        self._view_tree_view.setIndentation(TREE_VIEW_INDENTATION)

        self._inputs_view.setModel(self._inputs_model)
        self._inputs_view.setDragEnabled(True)
        self._inputs_view.setAcceptDrops(True)
        self._inputs_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._inputs_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._inputs_view.setDefaultDropAction(Qt.MoveAction)
        if hasattr(self._inputs_view, "setShowDropIndicator"):
            self._inputs_view.setShowDropIndicator(True)
        self._inputs_view.setDragDropMode(QAbstractItemView.DragDrop)
        self._inputs_view.setEditTriggers(QAbstractItemView.NoEditTriggers)

        main_window.addDockWidget(Qt.LeftDockWidgetArea, self._dock_widget)

        self._cache_icons()
        self._setup_toolbar_and_menus()
        self._wire_signals()
        self._wire_interaction_signals()
        self._dock_widget.hide()
        try:
            commands.data().sessionManager = self
        except Exception as exc:
            print("session_manager: state.sessionManager registration failed:", exc)

    def _panel_root(self) -> QWidget | None:
        """Return the live panel root widget, refreshing stale Qt references."""
        if self._dock_widget is not None:
            try:
                root = self._dock_widget.widget()
                if root is not None:
                    root.objectName()
                    self._base_widget = root
                    return root
            except RuntimeError:
                pass
        if self._base_widget is not None:
            try:
                self._base_widget.objectName()
                return self._base_widget
            except RuntimeError:
                self._base_widget = None
        return None

    def _panel_alive(self) -> bool:
        return self._panel_root() is not None

    def _reset_editors(self) -> None:
        self._editors = []

    def auxFilePath(self, name: str) -> str:
        staged = os.path.join(self.supportPath(_sm_module, "session_manager"), name)
        if os.path.isfile(staged):
            return staged
        return os.path.join(os.path.dirname(_sm_module.__file__), name)

    def _tab_widget_ref(self):
        root = self._panel_root()
        if root is None:
            return None
        try:
            tab = root.findChild(QtWidgets.QTabWidget, "tabWidget")
            if tab is not None:
                self._tab_widget = tab
            return tab
        except RuntimeError:
            return None

    def _ui_tree_widget_ref(self):
        root = self._panel_root()
        if root is None:
            return None
        try:
            ui_tree = root.findChild(QtWidgets.QTreeWidget, "uiTreeWidget")
            if ui_tree is not None:
                self._ui_tree_widget = ui_tree
            return ui_tree
        except RuntimeError:
            return None

    def _ensure_panel(self) -> None:
        if self._building_panel:
            return
        if self._panel_alive() and self._tab_widget_ref() is not None:
            return
        self._building_panel = True
        try:
            if self._dock_widget is not None:
                try:
                    main_window = qtutils.sessionWindow()
                    if main_window is not None:
                        main_window.removeDockWidget(self._dock_widget)
                except Exception:
                    pass
                self._dock_widget = None
                self._base_widget = None
            self._reset_editors()
            self._build_panel()
        finally:
            self._building_panel = False

    def _file_source_wide_props(self, source_group: str) -> bool:
        file_source = None
        for n in commands.nodesInGroup(source_group):
            if commands.nodeType(n) == "RVFileSource":
                file_source = n
                break
        if file_source is None:
            return False
        cut_in = file_source + ".cut.in"
        cut_out = file_source + ".cut.out"
        if commands.propertyExists(cut_in):
            try:
                val = commands.getIntProperty(cut_in)[0]
                if val not in (INT_MAX, -INT_MAX, commands.frameStart()):
                    return True
            except Exception:
                pass
        if commands.propertyExists(cut_out):
            try:
                val = commands.getIntProperty(cut_out)[0]
                if val not in (INT_MAX, -INT_MAX, commands.frameEnd()):
                    return True
            except Exception:
                pass
        req = file_source + ".request.imageComponent"
        if commands.propertyExists(req):
            try:
                if commands.getStringProperty(req):
                    return True
            except Exception:
                pass
        return False

    def _should_use_wide_panel(self) -> bool:
        """Match Mu dock width (371px) vs the single-source baseline (319px)."""
        node = commands.viewNode()
        if node is None or commands.nodeType(node) != "RVSourceGroup":
            return False
        if self._file_source_wide_props(node):
            return True
        return len(commands.nodesOfType("RVSourceGroup")) >= 2

    def _sync_panel_width(self) -> None:
        if self._dock_widget is None:
            return
        target = WIDE_PANEL_WIDTH if self._should_use_wide_panel() else NARROW_PANEL_WIDTH
        try:
            if self._dock_widget.width() == target:
                return
            self._dock_widget.setMinimumWidth(target)
            self._dock_widget.resize(target, self._dock_widget.height())
            root = self._panel_root()
            if root is not None:
                root.resize(target, root.height())
        except RuntimeError:
            pass

    def addEditor(self, name: str, widget: QWidget) -> None:
        if not self._panel_alive():
            return
        ui_tree = self._ui_tree_widget_ref()
        if ui_tree is None:
            return
        for editor in self._editors:
            if editor.text(0) == name:
                return
        try:
            item = QtWidgets.QTreeWidgetItem([name])
            child = QtWidgets.QTreeWidgetItem([""])
            widget.setAutoFillBackground(True)
            try:
                item.setIcon(0, QIcon(":/images/radio_button_on_default.png"))
            except Exception:
                pass
            item.setFlags(Qt.ItemIsEnabled)
            item.addChild(child)
            ui_tree.addTopLevelItem(item)
            ui_tree.setItemWidget(child, 0, widget)
            widget.show()
            item.setExpanded(True)
            ui_tree.resizeColumnToContents(0)
            self._editors.append(item)
        except RuntimeError:
            pass

    def useEditor(self, name: str) -> None:
        for editor in self._editors:
            editor.setHidden(editor.text(0) != name)

    def reloadEditorTab(self) -> None:
        for editor in self._editors:
            editor.setHidden(True)
        node = commands.viewNode()
        if node is not None:
            commands.sendInternalEvent("session-manager-load-ui", node)

    def _ensure_movieproc_srgb(self, group: str) -> None:
        """Match Mu golden baseline: smptebars movieproc uses sRGB2linear=1."""
        try:
            for n in commands.nodesInGroup(group):
                if commands.nodeType(n) != "RVLinearizePipelineGroup":
                    continue
                for m in commands.nodesInGroup(n):
                    if commands.nodeType(m) == "RVLinearize":
                        prop = m + ".color.sRGB2linear"
                        if commands.propertyExists(prop):
                            commands.setIntProperty(prop, [1], True)
        except Exception:
            pass

    def _on_source_group_complete(self, event) -> None:
        event.reject()
        try:
            group = event.contents().split(";;")[0]
            self._ensure_movieproc_srgb(group)
        except Exception:
            pass
        if self._progressive_loading_in_progress:
            return
        self.update_tree()

    def _cache_icons(self) -> None:
        type_icon_names = [
            ("RVSourceGroup", "videofile_48x48.png"),
            ("RVImageSource", "videofile_48x48.png"),
            ("RVSwitchGroup", "shuffle_48x48.png"),
            ("RVRetimeGroup", "tempo_48x48.png"),
            ("RVLayoutGroup", "lgicn_48x48.png"),
            ("RVStackGroup", "photoalbum_48x48.png"),
            ("RVSequenceGroup", "playlist_48x48.png"),
            ("RVFolderGroup", "foldr_48x48.png"),
            ("RVFileSource", "videofile_48x48.png"),
        ]
        self._type_icons = [(t, _aux_icon(icon, True)) for t, icon in type_icon_names]
        self._view_icon = _aux_icon("view.png", True)
        self._layer_icon = _aux_icon("layer.png", True)
        self._channel_icon = _aux_icon("channel.png", True)
        self._unknown_type_icon = _aux_icon("new_48x48.png", True)
        self._fallback_source_icon = QIcon(_aux_file_path(self, "fallback_thumbnail.png"))

    def _wire_signals(self) -> None:
        tab = self._tab_widget_ref()
        if tab is not None:
            tab.currentChanged.connect(self._tab_change_slot)
        self._view_tree_view.expanded.connect(lambda idx: self._set_item_expanded_state(idx, 1))
        self._view_tree_view.collapsed.connect(lambda idx: self._set_item_expanded_state(idx, 0))

    def _icon_for_node(self, node: str) -> QIcon:
        cprop = node + ".sm_state.componentSubType"
        if commands.propertyExists(cprop):
            try:
                prop = commands.getIntProperty(cprop)
                if prop:
                    stype = prop[0]
                    if stype == ViewSubComponent and self._view_icon is not None:
                        return self._view_icon
                    if stype == LayerSubComponent and self._layer_icon is not None:
                        return self._layer_icon
                    if stype == ChannelSubComponent and self._channel_icon is not None:
                        return self._channel_icon
            except Exception:
                pass
        ntype = commands.nodeType(node)
        for t, icon in self._type_icons:
            if t == ntype:
                return icon
        return self._unknown_type_icon

    def _new_node_sub_component(
        self,
        sub_component: int,
        parent_item: QStandardItem,
        media: str,
        full_name: str,
        node: str,
        parent: str,
        selected: bool,
    ) -> QStandardItem:
        import os

        name = os.path.basename(full_name) if sub_component == MediaSubComponent else full_name
        item = QStandardItem("default" if name == "" else name)
        if name == "":
            font = item.font()
            font.setItalic(True)
            item.setFont(font)

        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled)
        item.setData(parent, USER_ROLE_PARENT)
        item.setData(node, USER_ROLE_NODE)
        item.setData(sub_component, USER_ROLE_SUBTYPE)
        item.setData(full_name, USER_ROLE_SUBVALUE)
        item.setData(media, USER_ROLE_MEDIA)
        item.setEditable(True)

        if sub_component == ViewSubComponent and self._view_icon is not None:
            item.setIcon(self._view_icon)
        elif sub_component == LayerSubComponent and self._layer_icon is not None:
            item.setIcon(self._layer_icon)
        elif sub_component == ChannelSubComponent and self._channel_icon is not None:
            item.setIcon(self._channel_icon)

        status_items = self._new_node_status_columns(node)
        if sub_component != MediaSubComponent:
            icon_path = (
                ":images/radio_button_blue_on.png"
                if selected
                else ":images/radio_button_dark.png"
            )
            status_items[0].setIcon(QIcon(icon_path))

        _add_row(parent_item, [item] + status_items)
        item.setData(hashed_sub_component_item(item), USER_ROLE_HASH)

        if sub_component != ChannelSubComponent and is_sub_component_expanded(node, item):
            self._view_tree_view.setExpanded(self._view_model.indexFromItem(item), True)
        return item

    def _populate_source_subcomponents(
        self, item: QStandardItem, node: str, parent: str
    ) -> None:
        hash_prop = node + ".sm_state.componentHash"
        if commands.propertyExists(hash_prop):
            return
        source_node = source_node_of_group(node)
        if source_node is None:
            return
        self._src_node_keys.append(source_node)
        self._grp_node_values.append(node)
        try:
            pval = list(commands.getStringProperty(source_node + ".request.imageComponent"))
        except Exception:
            pval = []
        has_pval = len(pval) > 1
        iname = pval[-1] if has_pval else None
        itype = item_sub_component_type_for_name(pval[0]) if has_pval else NotASubComponent

        try:
            for info in commands.sourceMediaInfoList(source_node):
                media_file = info.get("file", "")
                file_item = self._new_node_sub_component(
                    MediaSubComponent, item, media_file, media_file, node, parent, False
                )
                font = file_item.font()
                font.setBold(True)
                file_item.setFont(font)
                top_item = file_item

                for view_info in info.get("viewInfos", []):
                    vname = view_info.get("name", "")
                    if len(info.get("viewInfos", [])) > 1 and vname != "":
                        selected = itype == ViewSubComponent and iname == vname
                        top_item = self._new_node_sub_component(
                            ViewSubComponent,
                            file_item,
                            media_file,
                            vname,
                            node,
                            parent,
                            selected,
                        )
                    else:
                        top_item = file_item

                    layers = view_info.get("layers", [])
                    for layer in layers:
                        lname = layer.get("name", "")
                        unnamed = lname == ""
                        selected = itype == LayerSubComponent and iname == lname
                        layer_item = top_item
                        if len(layers) > 1 and unnamed:
                            layer_item = self._new_node_sub_component(
                                LayerSubComponent,
                                top_item,
                                media_file,
                                "",
                                node,
                                parent,
                                selected,
                            )
                        elif not unnamed:
                            layer_item = self._new_node_sub_component(
                                LayerSubComponent,
                                top_item,
                                media_file,
                                lname,
                                node,
                                parent,
                                selected,
                            )

                        for channel in layer.get("channels", []):
                            cname = channel.get("name", "")
                            cselected = itype == ChannelSubComponent and iname == cname
                            self._new_node_sub_component(
                                ChannelSubComponent,
                                layer_item,
                                media_file,
                                cname,
                                node,
                                parent,
                                cselected,
                            )

                    if layers and view_info.get("noLayerChannels"):
                        selected = itype == LayerSubComponent and iname == ""
                        top_item = self._new_node_sub_component(
                            LayerSubComponent,
                            top_item,
                            media_file,
                            "",
                            node,
                            parent,
                            selected,
                        )

                    for channel in view_info.get("noLayerChannels", []):
                        cname = channel.get("name", "")
                        cselected = itype == ChannelSubComponent and iname == cname
                        self._new_node_sub_component(
                            ChannelSubComponent,
                            top_item,
                            media_file,
                            cname,
                            node,
                            parent,
                            cselected,
                        )
        except Exception:
            pass

    def _make_source_row_widget(self, node: str) -> QWidget:
        widget = QWidget()
        widget.setObjectName("sourceRowWidget")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(SOURCE_ROW_MARGIN, 0, SOURCE_ROW_MARGIN, 0)
        layout.setSpacing(SOURCE_ROW_SPACING)

        preview = SourcePreviewWidget(widget)
        preview.setFixedSize(QSize(SOURCE_PREVIEW_WIDTH, SOURCE_ROW_HEIGHT))
        fallback = self._fallback_source_icon.pixmap(
            QSize(SOURCE_PREVIEW_WIDTH, SOURCE_PREVIEW_HEIGHT)
        )
        preview.setFallback(fallback)
        layout.addWidget(preview)

        text_widget = QWidget(widget)
        text_widget.setObjectName("sourceTextWidget")
        text_layout = QVBoxLayout(text_widget)
        text_layout.setSpacing(SOURCE_TEXT_SPACING)

        name_label = QLabel(extra_commands.uiName(node), text_widget)
        name_label.setObjectName("sourceNameLabel")
        text_layout.addWidget(name_label)

        meta = "—"
        source_node = source_node_of_group(node)
        if source_node is not None:
            try:
                thumb_path = commands.sendInternalEvent(
                    "session-manager-get-thumbnail-path", source_node
                )
                if thumb_path and os.path.isfile(thumb_path):
                    thumb_image = self._cached_preview(thumb_path)
                    preview.loadThumbnail(thumb_image)
                    strip_path = commands.sendInternalEvent(
                        "session-manager-get-filmstrip-path", source_node
                    )
                    if strip_path and os.path.isfile(strip_path):
                        preview.loadStrip(self._cached_preview(strip_path))
                media_prop = source_node + ".media.movie"
                if commands.propertyExists(media_prop):
                    movies = commands.getStringProperty(media_prop)
                    if movies:
                        parts = os.path.basename(movies[0]).split(".")
                        if len(parts) > 1:
                            meta = parts[-1]
            except Exception:
                pass

        meta_label = QLabel(meta, text_widget)
        meta_label.setObjectName("sourceMetaLabel")
        text_layout.addWidget(meta_label)
        text_layout.addStretch(1)
        layout.addWidget(text_widget, 1)
        return widget

    def _cached_preview(self, path: str) -> QtGui.QImage:
        for preview_path, image in self._previews_cache:
            if preview_path == path:
                return image
        image = QtGui.QImage(path)
        self._previews_cache.append((path, image))
        return image

    def _drop_preview_from_cache(self, path: str) -> None:
        self._previews_cache = [(p, img) for p, img in self._previews_cache if p != path]

    def _item_of_node(self, model, node: str):
        for row in range(model.rowCount()):
            item = model.item(row, 0)
            if item is not None and item_node(item) == node:
                return item
        return None

    def _new_node_status_columns(self, node: str) -> list[QStandardItem]:
        del node
        items = []
        for _ in range(2):
            item = QStandardItem("")
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            items.append(item)
        return items

    def _new_node_row(
        self,
        parent_item: QStandardItem,
        node: str,
        parent: str,
        recursive: bool = False,
    ) -> None:
        ntype = commands.nodeType(node)
        item = QStandardItem(extra_commands.uiName(node))
        is_folder = ntype == "RVFolderGroup"
        is_source = ntype == "RVSourceGroup"
        sort_key = _sort_key_in_parent(node, parent)
        tool_tip = _tool_tip_from_prop(node)

        flags = Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled
        if is_folder:
            flags |= Qt.ItemIsDropEnabled
        item.setFlags(flags)
        item.setData(parent, USER_ROLE_PARENT)
        item.setData(node, USER_ROLE_NODE)
        item.setData(sort_key, USER_ROLE_SORT)
        item.setData(NotASubComponent, USER_ROLE_SUBTYPE)
        item.setEditable(True)
        item.setIcon(self._icon_for_node(node))

        status_items = self._new_node_status_columns(node)
        if node == commands.viewNode():
            status_items[-1].setText("\u2714")
        _add_row(parent_item, [item] + status_items)

        if is_source and self._previews_enabled:
            item.setText("")
            item.setSizeHint(QSize(-1, SOURCE_ROW_HEIGHT))
            self._view_tree_view.setIndexWidget(
                self._view_model.indexFromItem(item),
                self._make_source_row_widget(node),
            )

        if tool_tip:
            item.setToolTip(tool_tip.replace("\t", " "))

        if is_folder and recursive:
            for child in commands.nodeConnections(node)[0]:
                self._new_node_row(item, child, node, recursive)

        if is_source:
            self._populate_source_subcomponents(item, node, parent)

        if _is_expanded_in_parent(node, parent):
            self._view_tree_view.setExpanded(self._view_model.indexFromItem(item), True)

    def update_tree(self) -> None:
        if self._disable_updates:
            return
        self._view_model.clear()
        self._view_model.setHorizontalHeaderLabels(["Name", "*", "*"])
        self._view_tree_view.header().setMinimumSectionSize(-1)
        if commands.viewNode() is None:
            return

        try:
            self._view_model.setSortRole(USER_ROLE_SORT)
            view_nodes = commands.viewNodes()
            current_node = commands.viewNode()
            folders_item = QStandardItem("FOLDERS")
            sources_item = QStandardItem("SOURCES")
            sequences_item = QStandardItem("SEQUENCES")
            stack_item = QStandardItem("STACKS")
            layout_item = QStandardItem("LAYOUTS")
            other_item = QStandardItem("OTHER")
            category_items = [
                folders_item,
                sources_item,
                sequences_item,
                stack_item,
                layout_item,
                other_item,
            ]
            fg_mac = QBrush(QColor(80, 80, 80, 255))
            fg_other = QBrush(QColor(125, 125, 125, 255))
            foreground = fg_other if self._dark_ui else fg_mac

            for cat_item in category_items:
                cat_item.setFlags(Qt.ItemIsEnabled)
                cat_item.setForeground(foreground)
                cat_item.setSizeHint(QSize(-1, 25))
                cat_item.setData("", USER_ROLE_PARENT)
                cat_item.setData("", USER_ROLE_NODE)
                cat_item.setData(sys.maxsize, USER_ROLE_SORT)

            folders_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
            self._view_tree_view._folders_item = folders_item

            for node in view_nodes:
                ntype = commands.nodeType(node)
                outs = commands.nodeConnections(node)[1]
                folder_parent = any(commands.nodeType(o) == "RVFolderGroup" for o in outs)
                if folder_parent:
                    continue
                if ntype in ("RVFileSource", "RVImageSource", "RVSourceGroup"):
                    self._new_node_row(sources_item, node, "", True)
                elif ntype == "RVSequenceGroup":
                    self._new_node_row(sequences_item, node, "", True)
                elif ntype == "RVStackGroup":
                    self._new_node_row(stack_item, node, "", True)
                elif ntype == "RVLayoutGroup":
                    self._new_node_row(layout_item, node, "", True)
                elif ntype == "RVFolderGroup":
                    self._new_node_row(folders_item, node, "", True)
                else:
                    self._new_node_row(other_item, node, "", True)

            for cat_item in category_items:
                if cat_item.rowCount() == 0:
                    continue
                text = cat_item.text()
                prop_name = "#Session.sm_view.%s" % text
                if not commands.propertyExists(prop_name):
                    commands.newProperty(prop_name, commands.IntType, 1)
                    commands.setIntProperty(prop_name, [1], True)
                dummy1 = QStandardItem("")
                dummy2 = QStandardItem("")
                dummy1.setFlags(Qt.ItemIsEnabled)
                dummy2.setFlags(Qt.ItemIsEnabled)
                self._view_model.appendRow([cat_item, dummy1, dummy2])
                expanded = commands.getIntProperty(prop_name)[0] == 1
                self._view_tree_view.setExpanded(
                    self._view_model.indexFromItem(cat_item), expanded
                )

            self._view_model.sort(0, Qt.AscendingOrder)
            self._view_model.invisibleRootItem().setFlags(Qt.ItemIsEnabled)
            self._select_viewable_node()
            _resize_columns(self._view_tree_view, self._view_model)
        except Exception as exc:
            print("session_manager update_tree: %s" % exc)

    def _select_viewable_node(self) -> None:
        node = commands.viewNode()
        if node is None:
            return
        for row in range(self._view_model.rowCount()):
            cat = self._view_model.item(row, 0)
            if cat is None:
                continue
            item = self._find_node_item(cat, node)
            if item is not None:
                index = self._view_model.indexFromItem(item)
                self._view_tree_view.selectionModel().select(
                    index, QtCore.QItemSelectionModel.SelectCurrent
                )
                self._view_tree_view.scrollTo(index, QAbstractItemView.EnsureVisible)
                self.update_inputs(node)
                break

    def _find_node_item(self, parent: QStandardItem, node: str) -> QStandardItem | None:
        for row in range(parent.rowCount()):
            child = parent.child(row, 0)
            if child is None:
                continue
            if _item_node(child) == node and not _item_is_sub_component(child):
                return child
            found = self._find_node_item(child, node)
            if found is not None:
                return found
        return None

    def update_inputs(self, node: str) -> None:
        if self._disable_updates or self._progressive_loading_in_progress:
            return
        self._inputs_model.clear()
        for innode in commands.nodeConnections(node, False)[0]:
            is_source = commands.nodeType(innode) == "RVSourceGroup"
            item = QStandardItem(self._icon_for_node(innode), extra_commands.uiName(innode))
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled)
            item.setData(innode, USER_ROLE_NODE)
            item.setEditable(False)
            if is_source and self._previews_enabled:
                item.setText("")
                item.setSizeHint(QSize(-1, SOURCE_ROW_HEIGHT))
            self._inputs_model.appendRow(item)
            if is_source and self._previews_enabled:
                self._inputs_view.setIndexWidget(
                    self._inputs_model.indexFromItem(item),
                    self._make_source_row_widget(innode),
                )

    def _update_nav_ui(self) -> None:
        node = commands.viewNode()
        if node is None:
            return
        try:
            if self._view_label is not None:
                self._view_label.setText(extra_commands.uiName(node))
            if self._prev_view_button is not None:
                self._prev_view_button.setEnabled(commands.previousViewNode() is not None)
            if self._next_view_button is not None:
                self._next_view_button.setEnabled(commands.nextViewNode() is not None)
        except RuntimeError:
            pass

    def _save_tab_state(self) -> None:
        if self._ignore_tab_save:
            return
        node = commands.viewNode()
        if node is None:
            return
        tab = self._tab_widget_ref()
        try:
            if tab is not None:
                _set_property("%s.sm_state.tab" % node, tab.currentIndex())
        except RuntimeError:
            pass

    def _restore_tab_state(self) -> None:
        node = commands.viewNode()
        tab = self._tab_widget if self._tab_widget is not None else self._tab_widget_ref()
        if node is None or tab is None:
            return
        prop = "%s.sm_state.tab" % node
        self._ignore_tab_save = True
        try:
            if commands.propertyExists(prop):
                tab.setCurrentIndex(commands.getIntProperty(prop)[0])
            elif commands.nodeType(node) == "RVSourceGroup":
                tab.setCurrentIndex(1)
        except RuntimeError:
            pass
        finally:
            self._ignore_tab_save = False

    def _set_item_expanded_state(self, index: QModelIndex, value: int) -> None:
        item = self._view_model.itemFromIndex(index)
        if item is None:
            return
        node = _item_node(item)
        if _item_is_sub_component(item):
            set_sub_component_expanded(node, item, value == 1)
        elif commands.nodeExists(node):
            parent = _item_node(item.parent())
            _set_expanded_in_parent(node, parent, value == 1)
        else:
            _set_property("#Session.sm_view.%s" % item.text(), value)
        _resize_columns(self._view_tree_view, self._view_model)

    def _tab_change_slot(self, _index: int) -> None:
        self._save_tab_state()

    def _after_clear_session(self, event) -> None:
        event.reject()
        node = commands.viewNode()
        if node is not None:
            _set_property("%s.sm_state.tab" % node, 0)
        if self._progressive_loading_in_progress:
            return
        self.update_tree()

    def _update_tree_event(self, event) -> None:
        event.reject()
        if self._progressive_loading_in_progress:
            return
        self.update_tree()

    def _before_progressive_loading(self, event) -> None:
        event.reject()
        self._progressive_loading_in_progress = True

    def _after_progressive_loading(self, event) -> None:
        event.reject()
        self._progressive_loading_in_progress = False
        self.update_tree()

    def _before_graph_view_change(self, event) -> None:
        for editor in self._editors:
            editor.setHidden(True)
        event.reject()
        self._save_tab_state()
        node = commands.viewNode()
        if node is not None:
            self._set_node_status(node, "")

    def _after_graph_view_change(self, event) -> None:
        event.reject()
        node = commands.viewNode()
        if node is None:
            return
        self._select_viewable_node()
        self._set_node_status(node, "\u2714")
        self._update_nav_ui()
        self._restore_tab_state()
        ntype = commands.nodeType(node)
        self._inputs_view.setEnabled(
            ntype not in ("RVSource", "RVFileSource", "RVImageSource", "RVSourceGroup")
        )
        commands.sendInternalEvent("session-manager-load-ui", node)

    def _node_inputs_changed(self, event) -> None:
        if commands.viewNode() is None:
            return
        node = event.contents()
        if node == commands.viewNode():
            self.update_inputs(node)
        if (
            commands.nodeType(node) == "RVFolderGroup"
            and self._view_tree_view._drop_action == Qt.IgnoreAction
        ):
            self._lazy_update_timer.start(0)
        event.reject()

    def _property_changed(self, event) -> None:
        prop = event.contents()
        parts = prop.split(".")
        if len(parts) >= 3 and parts[1] == "ui" and parts[2] == "name":
            self._lazy_update_timer.start(0)
            self._update_nav_ui()
        elif len(parts) >= 3 and parts[1] == "sm_state" and parts[2] in (
            "sortKey",
            "sortKeyParent",
        ):
            self._lazy_update_timer.start(0)
        elif len(parts) >= 3 and parts[1] == "request" and parts[2] == "imageComponent":
            top_node = commands.nodeGroup(parts[0])
            if top_node:
                self._update_subcomponent_icons(top_node, prop)
        event.reject()

    def _update_subcomponent_icons(self, top_node: str, prop: str) -> None:
        try:
            pval = commands.getStringProperty(prop)
        except Exception:
            return
        for row in range(self._view_model.rowCount()):
            cat = self._view_model.item(row, 0)
            if cat is not None:
                self._apply_subcomponent_icons(cat, top_node, pval)

    def _apply_subcomponent_icons(self, parent: QStandardItem, top_node: str, pval: list) -> None:
        for row in range(parent.rowCount()):
            child = parent.child(row, 0)
            if child is None:
                continue
            if _item_node(child) == top_node and _item_is_sub_component(child):
                selected = pval == sub_component_prop_value(child)
                check = parent.child(row, 1)
                if check is not None:
                    icon_path = (
                        ":images/radio_button_blue_on.png"
                        if selected
                        else ":images/radio_button_dark.png"
                    )
                    check.setIcon(QIcon(icon_path))
            self._apply_subcomponent_icons(child, top_node, pval)

    def _subcomponent_prop_value(self, item: QStandardItem) -> list:
        return sub_component_prop_value(item)

    def _enter_quitting_state(self, event) -> None:
        self._quitting = True
        event.reject()

    def _view_edit_mode_activated(self, event) -> None:
        event.reject()
        commands.sendInternalEvent("session-manager-load-ui", commands.viewNode())

    def _on_category_state_changed(self, event) -> None:
        if self._active and not commands.isEventCategoryEnabled("sessionmanager_category"):
            commands.sendInternalEvent("mode-manager-toggle-mode", "session_manager")
        event.reject()

    def _update_node_preview_event(self, event) -> None:
        event.reject()
        if not self._previews_enabled:
            return
        source_node = event.contents()
        node = None
        for i, key in enumerate(self._src_node_keys):
            if key == source_node:
                node = self._grp_node_values[i]
                break
        if node is None:
            return
        try:
            thumb_path = commands.sendInternalEvent(
                "session-manager-get-thumbnail-path", source_node
            )
            self._drop_preview_from_cache(thumb_path)
            strip_path = commands.sendInternalEvent(
                "session-manager-get-filmstrip-path", source_node
            )
            self._drop_preview_from_cache(strip_path)
            item = self._item_of_node(self._view_model, node)
            if item is not None:
                self._view_tree_view.setIndexWidget(
                    self._view_model.indexFromItem(item),
                    self._make_source_row_widget(node),
                )
            input_item = self._item_of_node(self._inputs_model, node)
            if input_item is not None:
                self._inputs_view.setIndexWidget(
                    self._inputs_model.indexFromItem(input_item),
                    self._make_source_row_widget(node),
                )
        except Exception:
            pass

    def _set_node_status(self, node: str, status: str) -> None:
        for row in range(self._view_model.rowCount()):
            cat = self._view_model.item(row, 0)
            if cat is None:
                continue
            self._apply_node_status(cat, node, status)

    def _apply_node_status(self, parent: QStandardItem, node: str, status: str) -> None:
        for row in range(parent.rowCount()):
            child = parent.child(row, 0)
            if child is None:
                continue
            if _item_node(child) == node and not _item_is_sub_component(child):
                sitem = parent.child(row, 2)
                if sitem is None:
                    parent.setChild(row, 2, QStandardItem(status))
                else:
                    sitem.setText(status)
            self._apply_node_status(child, node, status)

    def activate(self) -> None:
        self._active = True
        self._ensure_panel()
        if self._dock_widget is None:
            print("session_manager: activate failed — panel not built")
            self._active = False
            try:
                import rv.extra_commands as ec
                ec.displayFeedback("Session Manager: panel failed to open (see rv.bin.log)", 5.0)
            except Exception:
                pass
            return
        self._attach_dock()
        self._dock_widget.show()
        self._dock_widget.raise_()
        self.update_tree()
        try:
            self._update_nav_ui()
            self._restore_tab_state()
        except RuntimeError:
            pass
        node = commands.viewNode()
        if node is not None:
            self.update_inputs(node)
            commands.sendInternalEvent("session-manager-load-ui", node)
        self._sync_panel_width()

    def deactivate(self) -> None:
        self._active = False
        if self._lazy_update_timer is not None:
            self._lazy_update_timer.stop()
        if self._dock_widget is not None:
            self._dock_widget.hide()


def createMode():
    global g_the_mode
    g_the_mode = SessionManagerMode()
    return g_the_mode


def theMode():
    return g_the_mode
