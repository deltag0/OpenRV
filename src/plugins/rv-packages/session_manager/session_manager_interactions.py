#
# Interactive UI wiring and handlers for session_manager (Mu port).
#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import os
import re
import sys

from rv import commands, extra_commands, qtutils

import sm_edit_support

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QModelIndex, QTimer
    from PySide6.QtGui import (
        QAction,
        QActionGroup,
        QDragEnterEvent,
        QDropEvent,
        QStandardItem,
    )
    from PySide6.QtWidgets import (
        QColorDialog,
        QListView,
        QMenu,
    )
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt, QModelIndex, QTimer
    from PySide2.QtGui import QAction, QDragEnterEvent, QDropEvent, QStandardItem
    from PySide2.QtWidgets import (
        QColorDialog,
        QListView,
        QMenu,
        QActionGroup,
    )

from session_manager_support import (
    MediaSubComponent,
    NotASubComponent,
    aux_icon,
    add_input,
    has_input,
    item_is_sub_component,
    item_node,
    item_parent_node,
    item_sub_component_type,
    node_from_index,
    node_inputs,
    remove_input,
    rename_by_type,
    set_image_request,
    set_inputs,
    set_sort_key_in_parent,
    sub_component_prop_value,
    source_from_sub_component,
)

_SORT_TIMER_MS = 200 if sys.platform == "win32" else 100


class InputsView(QListView):
    def __init__(self, tree_view, parent=None, drop_cleanup=None):
        super().__init__(parent)
        self._view_tree_view = tree_view
        self._drop_timer = QTimer(self)
        self._drop_timer.setSingleShot(True)
        if drop_cleanup is not None:
            self._drop_timer.timeout.connect(drop_cleanup)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.source() is self._view_tree_view:
            event.setDropAction(Qt.CopyAction)
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        super().dropEvent(event)
        if event.source() is self._view_tree_view:
            self._drop_timer.start(_SORT_TIMER_MS)


class SessionManagerInteractions:
    """Mixin: toolbar, menus, tree/input handlers, and dialogs."""

    def _init_interaction_state(self) -> None:
        self._view_context_menu = None
        self._view_context_menu_actions = []
        self._create_menu = None
        self._folder_menu = None
        self._new_node_dialog = None
        self._node_type_combo = None
        self._create_image_dialog = None
        self._color_dialog = None
        self._cid_fmt_spec = ""
        self._cid_name = ""
        self._cid_color = None
        self._lazy_set_inputs_timer = None
        self._main_win_vis_timer = None
        self._view_icon = None
        self._layer_icon = None
        self._channel_icon = None

    def _setup_toolbar_and_menus(self) -> None:
        root = self._panel_root()
        if root is None:
            return

        add_button = root.findChild(QtWidgets.QToolButton, "addButton")
        folder_button = root.findChild(QtWidgets.QToolButton, "folderButton")
        delete_button = root.findChild(QtWidgets.QToolButton, "deleteButton")
        config_button = root.findChild(QtWidgets.QToolButton, "configButton")
        edit_info_button = root.findChild(QtWidgets.QToolButton, "renameButton")
        home_button = root.findChild(QtWidgets.QToolButton, "selectCurrentButton")
        order_up = root.findChild(QtWidgets.QToolButton, "orderUpButton")
        order_down = root.findChild(QtWidgets.QToolButton, "orderDownButton")
        sort_asc = root.findChild(QtWidgets.QToolButton, "sortAscButton")
        sort_desc = root.findChild(QtWidgets.QToolButton, "sortDescButton")
        inputs_delete = root.findChild(QtWidgets.QToolButton, "inputsDeleteButton")

        if add_button is None:
            return

        def _set_default(button, action) -> None:
            if button is not None:
                button.setDefaultAction(action)

        dark = getattr(self, "_dark_ui", True)
        add_action = QAction(aux_icon("add_48x48.png", True, dark), "Create View", add_button)
        folder_action = QAction(aux_icon("foldr_48x48.png", True, dark), "Create Folder", folder_button)
        delete_action = QAction(aux_icon("trash_48x48.png", True, dark), "Delete View", delete_button)
        config_action = QAction(aux_icon("confg_48x48.png", True, dark), "Configure", config_button)
        edit_info_action = QAction(aux_icon("sinfo_48x48.png", True, dark), "Edit View Info", edit_info_button)
        order_up_action = QAction(aux_icon("up_48x48.png", True, dark), "Move Input Higher in List", order_up)
        order_down_action = QAction(aux_icon("down_48x48.png", True, dark), "Move Input Lower in List", order_down)
        sort_asc_action = QAction("A-Z", sort_asc)
        sort_desc_action = QAction("Z-A", sort_desc)
        inputs_delete_action = QAction(aux_icon("trash_48x48.png", True, dark), "Delete Input", inputs_delete)
        prev_view_action = QAction(aux_icon("back_48x48.png", True, dark), "Previous View", self._prev_view_button)
        next_view_action = QAction(aux_icon("forwd_48x48.png", True, dark), "Next View", self._next_view_button)
        home_action = QAction(aux_icon("home_48x48.png", True, dark), "Select Current View", home_button)

        _set_default(add_button, add_action)
        _set_default(delete_button, delete_action)
        _set_default(edit_info_button, edit_info_action)
        add_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        _set_default(config_button, config_action)
        if config_button is not None:
            config_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        _set_default(order_up, order_up_action)
        _set_default(order_down, order_down_action)
        _set_default(sort_asc, sort_asc_action)
        _set_default(sort_desc, sort_desc_action)
        _set_default(inputs_delete, inputs_delete_action)
        _set_default(self._prev_view_button, prev_view_action)
        _set_default(self._next_view_button, next_view_action)
        _set_default(home_button, home_action)

        add_menu = QMenu("New Viewable", add_button)
        add_sequence = add_menu.addAction(aux_icon("playlist_48x48.png", True, dark), "Sequence")
        add_stack = add_menu.addAction(aux_icon("photoalbum_48x48.png", True, dark), "Stack")
        add_switch = add_menu.addAction(aux_icon("shuffle_48x48.png", True, dark), "Switch")
        add_folder = add_menu.addAction(aux_icon("foldr_48x48.png", True, dark), "Folder")
        add_layout = add_menu.addAction(aux_icon("lgicn_48x48.png", True, dark), "Layout")
        add_retime = add_menu.addAction(aux_icon("tempo_48x48.png", True, dark), "Retime")
        add_colorize = add_menu.addAction(aux_icon("new_48x48.png", True, dark), "Color")
        add_ocio = add_menu.addAction(aux_icon("new_48x48.png", True, dark), "OCIO")
        add_dynamic = None
        if os.getenv("RV_ENABLE_DYNAMIC_NODE") is not None:
            add_dynamic = add_menu.addAction(aux_icon("new_48x48.png", True, dark), "Dynamic")
        add_user_node = add_menu.addAction(aux_icon("new_48x48.png", True, dark), "New Node by Type...")
        add_menu.addSeparator()
        add_srgb = add_menu.addAction(aux_icon("colorchart_48x48.png", True, dark), "SRGB Color Chart...")
        add_aces = add_menu.addAction(aux_icon("colorchart_48x48.png", True, dark), "ACES Color Chart...")
        add_cbars = add_menu.addAction(aux_icon("ntscbars_48x48.png", True, dark), "Color Bars...")
        add_black = add_menu.addAction(aux_icon("video_48x48.png", True, dark), "Black...")
        add_color = add_menu.addAction(aux_icon("video_48x48.png", True, dark), "Color...")
        add_blank = add_menu.addAction(aux_icon("video_48x48.png", True, dark), "Blank...")

        menu_actions = [
            (add_stack, "RVStackGroup"),
            (add_folder, "RVFolderGroup"),
            (add_layout, "RVLayoutGroup"),
            (add_sequence, "RVSequenceGroup"),
            (add_retime, "RVRetimeGroup"),
            (add_switch, "RVSwitchGroup"),
            (add_colorize, "RVColor"),
            (add_ocio, "RVOCIO"),
        ]
        if add_dynamic is not None:
            menu_actions.append((add_dynamic, "Dynamic"))
        menu_actions.extend(
            [
                (add_user_node, ""),
                (add_srgb, "srgbcolorchart,%s.movieproc"),
                (add_aces, "acescolorchart,%s.movieproc"),
                (add_cbars, "smptebars,%s.movieproc"),
                (add_black, "black,%s.movieproc"),
                (add_color, "solid,%s.movieproc"),
                (add_blank, "blank,%s.movieproc"),
            ]
        )

        add_button.setMenu(add_menu)
        add_button.setArrowType(Qt.NoArrow)
        self._create_menu = add_menu

        folder_menu = QMenu("New Folder", folder_button)
        new_folder = folder_menu.addAction("Empty Folder")
        new_folder2 = folder_menu.addAction("From Selection")
        new_folder3 = folder_menu.addAction("From Copy of Selection")
        _set_default(folder_button, folder_action)
        if folder_button is not None:
            folder_button.setMenu(folder_menu)
            folder_button.setArrowType(Qt.NoArrow)
            folder_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self._folder_menu = folder_menu

        config_menu = QMenu("Config", config_button)
        config_always = config_menu.addAction("Always Show at Start Up")
        config_never = config_menu.addAction("Never Show at Start Up")
        config_last = config_menu.addAction("Restore Last State at Start Up")
        config_group = QActionGroup(config_button)
        for action in (config_always, config_never, config_last):
            action.setCheckable(True)
            config_group.addAction(action)
        config_menu.addSeparator()
        preview_toggle = config_menu.addAction("Show Source Previews")
        preview_toggle.setCheckable(True)
        preview_toggle.setChecked(self._previews_enabled)
        if os.getenv("RV_SESSION_MANAGER_USE_THUMBNAILS") == "0":
            preview_toggle.setEnabled(False)
        if config_button is not None:
            config_button.setMenu(config_menu)

        try:
            state = commands.readSettings("SessionManager", "showOnStartup", "no")
            if state == "yes":
                config_always.setChecked(True)
            elif state == "last":
                config_last.setChecked(True)
            else:
                config_never.setChecked(True)
        except Exception:
            config_never.setChecked(True)

        for action, protocol in menu_actions:
            action.triggered.connect(lambda _checked=False, p=protocol: self._add_thing_slot(p))

        self._view_context_menu_actions = [delete_action, edit_info_action, home_action]
        home_action.triggered.connect(self._select_current_view_slot)
        delete_action.triggered.connect(self._delete_viewable_slot)
        edit_info_action.triggered.connect(self._edit_view_info_slot)
        order_up_action.triggered.connect(lambda: self._reorder_selected(True))
        order_down_action.triggered.connect(lambda: self._reorder_selected(False))
        sort_asc_action.triggered.connect(lambda: self._sort_inputs(True))
        sort_desc_action.triggered.connect(lambda: self._sort_inputs(False))
        inputs_delete_action.triggered.connect(self._inputs_delete_slot)
        prev_view_action.triggered.connect(lambda: self._nav_button_clicked("prev"))
        next_view_action.triggered.connect(lambda: self._nav_button_clicked("next"))
        new_folder.triggered.connect(lambda: self._new_folder_slot(1))
        new_folder2.triggered.connect(lambda: self._new_folder_slot(2))
        new_folder3.triggered.connect(lambda: self._new_folder_slot(3))
        config_always.triggered.connect(lambda: self._config_slot("yes", True))
        config_never.triggered.connect(lambda: self._config_slot("no", False))
        config_last.triggered.connect(lambda: self._config_slot("last", True))
        preview_toggle.toggled.connect(self._toggle_previews)

        self._color_dialog = QColorDialog(qtutils.sessionWindow())
        self._color_dialog.setOption(QColorDialog.ShowAlphaChannel, False)
        self._color_dialog.currentColorChanged.connect(self._new_color_slot)

    def _wire_interaction_signals(self) -> None:
        if self._lazy_set_inputs_timer is None and self._dock_widget is not None:
            self._lazy_set_inputs_timer = QTimer(self._dock_widget)
            self._lazy_set_inputs_timer.setSingleShot(True)
            self._lazy_set_inputs_timer.timeout.connect(self._rebuild_inputs_from_list)

            self._main_win_vis_timer = QTimer(self._dock_widget)
            self._main_win_vis_timer.setSingleShot(True)
            self._main_win_vis_timer.timeout.connect(self._main_win_vis_timeout)
            self._dock_widget.visibilityChanged.connect(self._visibility_changed)

        self._view_model.itemChanged.connect(self._view_item_changed)
        self._view_tree_view.customContextMenuRequested.connect(self._view_context_menu_slot)
        self._view_tree_view.doubleClicked.connect(lambda index: self._view_by_index(index, self._view_model))
        self._view_tree_view.pressed.connect(lambda index: self._item_pressed(index, self._view_model))
        self._inputs_view.doubleClicked.connect(lambda index: self._view_by_index(index, self._inputs_model))
        self._inputs_model.rowsRemoved.connect(self._input_rows_removed_slot)
        self._inputs_model.rowsInserted.connect(self._input_rows_inserted_slot)

    # --- Public API (Mu-compatible) ---

    def selectedNodes(self) -> list[str]:
        return self.selected_nodes()

    def selected_nodes(self) -> list[str]:
        nodes: list[str] = []
        for index in self._view_tree_view.selectionModel().selectedIndexes():
            if index.column() != 0:
                continue
            node = item_node(self._view_model.itemFromIndex(index))
            if commands.nodeExists(node):
                nodes.append(node)
        return nodes

    def selectedItems(self) -> list[QStandardItem]:
        return self.selected_items()

    def selected_items(self) -> list[QStandardItem]:
        items: list[QStandardItem] = []
        for index in self._view_tree_view.selectionModel().selectedIndexes():
            if index.column() == 0:
                item = self._view_model.itemFromIndex(index)
                if item is not None:
                    items.append(item)
        return items

    # --- View / tree handlers ---

    def _view_by_index(self, index: QModelIndex, model) -> None:
        item = model.itemFromIndex(index)
        if item is None:
            return
        node = item_node(item)
        sub_type = item_sub_component_type(item)
        self._disable_updates = True
        try:
            view_change = False
            if commands.viewNode() != node:
                commands.setViewNode(node)
                view_change = True
            if sub_type != NotASubComponent:
                set_image_request(sub_component_prop_value(item), not view_change)
        except Exception:
            pass
        self._disable_updates = False
        self.update_inputs(commands.viewNode())

    def _item_pressed(self, index: QModelIndex, model) -> None:
        item0 = model.itemFromIndex(index)
        sindex = index.sibling(index.row(), 0)
        item = model.itemFromIndex(sindex)
        if item is None:
            return
        sub_type = item_sub_component_type(item)
        if item0.column() == 1 and sub_type not in (NotASubComponent, MediaSubComponent):
            self._view_by_index(sindex, model)

    def _view_item_changed(self, item: QStandardItem) -> None:
        node = item_node(item)
        sub_type = item_sub_component_type(item)
        parent_item = item.parent()
        parent = item_node(parent_item) if parent_item is not None else ""
        node_paths = self._view_tree_view.filteredDraggedPaths(lambda p: p[0] == node)

        if self._view_tree_view._drop_action == Qt.CopyAction:
            if not has_input(parent, node):
                add_input(parent, node)
                item.setData(parent, Qt.UserRole + 1)
                if parent and commands.nodeType(parent) == "RVFolderGroup":
                    self._view_tree_view.sortFolderChildren(parent)
        elif self._view_tree_view._drop_action == Qt.MoveAction and node_paths:
            parent_exists = commands.nodeExists(parent)
            if parent_exists and not has_input(parent, node):
                add_input(parent, node)
            item.setData(parent if parent_exists else "", Qt.UserRole + 1)
            for path in node_paths:
                if len(path) > 1 and commands.nodeExists(path[1]):
                    if not parent_exists or path[1] != parent:
                        remove_input(path[1], path[0])
            if parent_exists and commands.nodeType(parent) == "RVFolderGroup":
                self._view_tree_view.sortFolderChildren(parent)
        elif node and sub_type == NotASubComponent:
            self._disable_updates = True
            try:
                commands.setUIName(node, item.text())
            except Exception as exc:
                print("failed to set name on %s to %s: %s\n" % (node, item.text(), exc))
            self._disable_updates = False

    def _view_context_menu_slot(self, pos) -> None:
        if self._view_context_menu is None:
            self._view_context_menu = QMenu(self._view_tree_view)
            if self._folder_menu is not None:
                folder_menu = self._view_context_menu.addMenu(self._folder_menu)
                folder_menu.setIcon(aux_icon("foldr_48x48.png", True, getattr(self, "_dark_ui", True)))
            if self._create_menu is not None:
                create_menu = self._view_context_menu.addMenu(self._create_menu)
                create_menu.setIcon(aux_icon("add_48x48.png", True, getattr(self, "_dark_ui", True)))
            for action in self._view_context_menu_actions:
                self._view_context_menu.addAction(action)
        self._view_context_menu.exec_(self._view_tree_view.mapToGlobal(pos))

    def _select_current_view_slot(self, _checked=False) -> None:
        self._select_viewable_node()

    def _edit_view_info_slot(self, _checked=False) -> None:
        indices = self._view_tree_view.selectionModel().selectedIndexes()
        if not indices:
            return
        self._view_tree_view.edit(indices[0])

    def _delete_viewable_slot(self, _checked=False) -> None:
        for item in self.selected_items():
            node = item_node(item)
            parent = item_parent_node(item)
            outs = commands.nodeConnections(node)[1]
            parent_type = commands.nodeType(parent) if commands.nodeExists(parent) else ""
            nfolders = sum(1 for o in outs if commands.nodeType(o) == "RVFolderGroup")
            if parent_type == "RVFolderGroup" and nfolders > 1:
                remove_input(parent, node)
            else:
                self._disable_updates = True
                try:
                    commands.deleteNode(node)
                except Exception as exc:
                    print("Error: %s, failed to delete '%s'\n" % (exc, node))
                self._disable_updates = False
        self._lazy_update_timer.start(0)

    def _nav_button_clicked(self, which: str, _checked=False) -> None:
        self._disable_updates = True
        try:
            if which == "next" and commands.nextViewNode() is not None:
                commands.setViewNode(commands.nextViewNode())
            if which == "prev" and commands.previousViewNode() is not None:
                commands.setViewNode(commands.previousViewNode())
        except Exception:
            pass
        self._disable_updates = False
        self.update_inputs(commands.viewNode())

    # --- Input list handlers ---

    def _select_inputs_range(self, selection_list: list[int]) -> None:
        smodel = self._inputs_view.selectionModel()
        for row in selection_list:
            index = self._inputs_model.index(row, 0, QModelIndex())
            smodel.select(index, QtCore.QItemSelectionModel.Select)

    def _reorder_selected(self, up: bool, _checked=False) -> None:
        indices = self._inputs_view.selectionModel().selectedIndexes()
        if not indices:
            return
        inputs = node_inputs(commands.viewNode())
        min_row = min(indices[0].row(), indices[-1].row())
        max_row = max(indices[0].row(), indices[-1].row())
        if (up and min_row == 0) or (not up and max_row == len(inputs) - 1):
            return

        num_rows = self._inputs_model.rowCount(QModelIndex())
        index_set = {idx.row() for idx in indices}
        selection_sizes: list[int] = []
        selection_size = 0
        for i in range(num_rows):
            included = i in index_set
            if included:
                selection_size += 1
            elif selection_size > 0 or selection_sizes:
                selection_sizes.append(selection_size)
                selection_size = 0
        if selection_size > 0:
            selection_sizes.append(selection_size)

        included_list: list[int] = []
        new_nodes: list[str | None] = [None] * num_rows
        size_index = 0
        included_inc = -1 if up else 1
        for i in range(num_rows):
            included = i in index_set
            new_index = i
            excluded_inc = -included_inc * selection_sizes[size_index] if selection_sizes else 0
            if included:
                new_index = i + included_inc
                included_list.append(new_index)
            elif min_row + included_inc <= i <= max_row + included_inc:
                new_index = i + excluded_inc
                if size_index < len(selection_sizes) - 1:
                    size_index += 1
            index = self._inputs_model.index(i, 0, QModelIndex())
            new_nodes[new_index] = node_from_index(index, self._inputs_model)

        try:
            set_inputs(commands.viewNode(), [n for n in new_nodes if n is not None])
            self._select_inputs_range(included_list)
        except Exception as exc:
            print("FAILED: %s\n" % exc)

    def _sort_inputs(self, up: bool, _checked=False) -> None:
        if self._input_order_lock or commands.viewNode() is None:
            return
        node = commands.viewNode()
        inputs = node_inputs(node)
        sorted_inputs: list[str] = []
        for source in inputs:
            media = extra_commands.uiName(source)
            found = False
            tmp: list[str] = []
            for s in sorted_inputs:
                order = (media > extra_commands.uiName(s)) - (media < extra_commands.uiName(s))
                if found or (up and order > 0) or (not up and order < 0):
                    tmp.append(s)
                else:
                    tmp.append(source)
                    tmp.append(s)
                    found = True
            if not found:
                sorted_inputs.append(source)
            else:
                sorted_inputs = tmp

        if not set_inputs(node, sorted_inputs):
            self.update_inputs(node)

        if commands.nodeType(node) == "RVFolderGroup":
            for i, n in enumerate(sorted_inputs):
                set_sort_key_in_parent(n, node, i)
            self.update_tree()

    def _inputs_delete_slot(self, _checked=False) -> None:
        if self._input_order_lock or commands.viewNode() is None:
            return
        indices = self._inputs_view.selectionModel().selectedIndexes()
        index_set = {idx.row() for idx in indices}
        inputs = node_inputs(commands.viewNode())
        new_nodes = []
        for i in range(len(inputs)):
            index = self._inputs_model.index(i, 0, QModelIndex())
            if i not in index_set:
                new_nodes.append(node_from_index(index, self._inputs_model))
        try:
            set_inputs(commands.viewNode(), new_nodes)
        except Exception as exc:
            print("FAILED: %s\n" % exc)

    def _input_rows_removed_slot(self, _parent, _start, _end) -> None:
        if self._input_order_lock or commands.viewNode() is None:
            return
        self._lazy_set_inputs_timer.start(100)

    def _input_rows_inserted_slot(self, _parent, _start, _end) -> None:
        if self._input_order_lock or commands.viewNode() is None:
            return
        self._lazy_set_inputs_timer.start(100)

    def _rebuild_inputs_from_list(self) -> None:
        if self._input_order_lock or commands.viewNode() is None:
            return
        num = self._inputs_model.rowCount(QModelIndex())
        nodes: list[str] = []
        vnode = commands.viewNode()
        self._disable_updates = True
        try:
            for row in range(num):
                item = self._inputs_model.item(row, 0)
                if item is None:
                    continue
                node = item_node(item)
                if not commands.nodeExists(node):
                    continue
                if item_is_sub_component(item):
                    try:
                        nodes.append(source_from_sub_component(item, node))
                    except Exception:
                        pass
                else:
                    nodes.append(node)
            if nodes and vnode:
                set_inputs(vnode, nodes)
        finally:
            self._disable_updates = False
            if vnode:
                commands.setViewNode(vnode)

    # --- Create / folder ---

    def _selected_converted_sub_components(self) -> list[str]:
        nodes: list[str] = []
        for index in self._view_tree_view.selectionModel().selectedIndexes():
            if index.column() != 0:
                continue
            item = self._view_model.itemFromIndex(index)
            node = item_node(item)
            if not commands.nodeExists(node):
                continue
            if item_is_sub_component(item):
                self._disable_updates = True
                try:
                    snode = source_from_sub_component(item, node)
                finally:
                    self._disable_updates = False
                nodes.append(snode)
            else:
                nodes.append(node)
        return nodes

    def _add_node_of_type(self, typename: str) -> str | None:
        nodes = self._selected_converted_sub_components()
        n = commands.newNode(typename, "")
        if n is None or not set_inputs(n, nodes):
            if n is not None:
                commands.deleteNode(n)
            return None
        rename_by_type(n, nodes)
        commands.setViewNode(n)
        return n

    def _add_node_by_type_name(self) -> None:
        if self._new_node_dialog is None:
            m = qtutils.sessionWindow()
            self._new_node_dialog = sm_edit_support.load_ui_file("new_node.ui", m)
            if self._new_node_dialog is None:
                return
            self._node_type_combo = self._new_node_dialog.findChild(QtWidgets.QComboBox, "comboBox")
            if self._node_type_combo is not None:
                self._node_type_combo.addItems(commands.nodeTypes(True))
            label = self._new_node_dialog.findChild(QtWidgets.QLabel, "pictureLabel")
            if label is not None:
                label.setPixmap(aux_icon("new_48x48.png", True, getattr(self, "_dark_ui", True)).pixmap(48, 48))
            self._new_node_dialog.accepted.connect(lambda: self._add_node_of_type(self._node_type_combo.currentText()))
        self._new_node_dialog.show()

    def _add_movie_proc(self, fmtspec: str) -> None:
        if self._create_image_dialog is None:
            m = qtutils.sessionWindow()
            self._create_image_dialog = sm_edit_support.load_ui_file("create_image_dialog.ui", m)
            if self._create_image_dialog is None:
                return
            self._cid_width = self._create_image_dialog.findChild(QtWidgets.QLineEdit, "widthEdit")
            self._cid_height = self._create_image_dialog.findChild(QtWidgets.QLineEdit, "heightEdit")
            self._cid_fps = self._create_image_dialog.findChild(QtWidgets.QLineEdit, "fpsEdit")
            self._cid_length = self._create_image_dialog.findChild(QtWidgets.QLineEdit, "lengthEdit")
            self._cid_pic = self._create_image_dialog.findChild(QtWidgets.QLabel, "pictureLabel")
            self._cid_group = self._create_image_dialog.findChild(QtWidgets.QGroupBox, "groupBox")
            self._cid_color_btn = self._create_image_dialog.findChild(QtWidgets.QPushButton, "colorButton")
            self._cid_color_label = self._create_image_dialog.findChild(QtWidgets.QLabel, "colorLabel")
            try:
                fps = commands.readSettings("General", "fps", 24.0)
                if self._cid_fps is not None:
                    self._cid_fps.setText(str(float(fps)))
            except Exception:
                pass
            self._create_image_dialog.accepted.connect(self._make_image_from_dialog)

        ptype = fmtspec.split(",")[0]
        self._cid_fmt_spec = fmtspec
        icon = aux_icon("video_48x48.png", True, getattr(self, "_dark_ui", True))
        self._cid_color = QtGui.QColor(128, 128, 128, 255)
        if self._cid_color_btn is not None:
            self._cid_color_btn.setVisible(ptype in ("black", "solid"))
            self._cid_color_btn.setEnabled(ptype == "solid")
        if self._cid_color_label is not None:
            self._cid_color_label.setVisible(ptype in ("black", "solid"))
            self._cid_color_label.setEnabled(ptype == "solid")

        names = {
            "srgbcolorchart": "SRGBMacbethColorChart",
            "acescolorchart": "ACESMacbethColorChart",
            "smptebars": "SMTPEColorBars",
            "blank": "Blank",
            "black": "Black",
            "solid": "SolidColor",
        }
        icons = {
            "srgbcolorchart": "colorchart_48x48.png",
            "acescolorchart": "colorchart_48x48.png",
            "smptebars": "ntscbars_48x48.png",
        }
        self._cid_name = names.get(ptype, "Source")
        if ptype in icons:
            icon = aux_icon(icons[ptype], True, getattr(self, "_dark_ui", True))
        if self._cid_pic is not None:
            self._cid_pic.setPixmap(icon.pixmap(48, 48))
        if self._cid_group is not None:
            self._cid_group.setTitle(self._cid_name)
        if self._cid_width is not None:
            self._cid_width.setVisible(ptype not in ("blank",))
        if self._cid_height is not None:
            self._cid_height.setVisible(ptype not in ("blank",))
        self._create_image_dialog.show()

    def _make_image_from_dialog(self) -> None:
        w = self._cid_width.text() if self._cid_width else "1920"
        h = self._cid_height.text() if self._cid_height else "1080"
        fps = self._cid_fps.text() if self._cid_fps else "24"
        length = self._cid_length.text() if self._cid_length else "48"
        color = self._cid_color or QtGui.QColor(128, 128, 128)
        mp = self._cid_fmt_spec % (
            "width=%s,height=%s,fps=%s,start=1,end=%s,red=%g,green=%g,blue=%g"
            % (w, h, fps, length, color.redF(), color.greenF(), color.blueF())
        )
        sources = commands.addSourceVerbose([mp])
        if sources:
            group = commands.nodeGroup(sources)
            commands.setUIName(group, self._cid_name)

    def _new_color_slot(self, color) -> None:
        self._cid_color = color
        if self._cid_color_btn is not None:
            self._cid_color_btn.setStyleSheet(
                "QPushButton { background-color: rgb(%d,%d,%d); }" % (color.red(), color.green(), color.blue())
            )

    def _add_thing_slot(self, thingstring: str, _checked=False) -> None:
        if re.search(r"\.movieproc$", thingstring):
            self._add_movie_proc(thingstring)
        elif thingstring == "":
            self._add_node_by_type_name()
        else:
            self._add_node_of_type(thingstring)

    def _new_folder_slot(self, which: int, _checked=False) -> None:
        paths = self._view_tree_view.selectedNodePaths()
        folder = commands.newNode("RVFolderGroup", "Folder")
        nodes = [path[0] for path in paths if path]
        if paths:
            first = paths[0]
            if which != 1 and nodes:
                if not set_inputs(folder, nodes):
                    if folder:
                        commands.deleteNode(folder)
                    return
            self._disable_updates = True
            if which == 2:
                for path in paths:
                    if len(path) > 1 and commands.nodeExists(path[1]):
                        remove_input(path[1], path[0])
            if len(first) > 1 and commands.nodeExists(first[1]):
                add_input(first[1], folder)
                set_sort_key_in_parent(folder, first[1], self._sort_key_in_parent(first[0], first[1]))
            self._disable_updates = False

        self._disable_updates = True
        rename_by_type(folder, [] if which == 1 else nodes)
        self._disable_updates = False
        if paths:
            commands.setViewNode(folder)

    def _sort_key_in_parent(self, node: str, parent: str) -> int:
        from session_manager_support import index_of

        prop_parent = "%s.sm_state.sortKeyParent" % node
        prop_key = "%s.sm_state.sortKey" % node
        undefined = sys.maxsize - 100
        if commands.propertyExists(prop_parent) and commands.propertyExists(prop_key):
            try:
                parents = list(commands.getStringProperty(prop_parent))
                keys = list(commands.getIntProperty(prop_key))
                idx = index_of(parents, parent)
                if idx != -1 and len(keys) == len(parents):
                    return keys[idx]
            except Exception:
                pass
        return undefined

    # --- Config / visibility ---

    def _config_slot(self, onstart: str, show: bool, _checked=False) -> None:
        try:
            commands.writeSettings("SessionManager", "showOnStartup", onstart)
            commands.writeSettings("Tools", "show_session_manager", show)
        except Exception:
            pass

    def _toggle_previews(self, checked: bool) -> None:
        self._previews_enabled = checked
        try:
            commands.writeSettings("SessionManager", "previewsEnabled", checked)
        except Exception:
            pass
        event = "session-manager-previews-disabled" if not checked else "session-manager-previews-enabled"
        commands.sendInternalEvent(event, "")
        self.update_tree()

    def _visibility_changed(self, _vis: bool) -> None:
        if self._main_win_vis_timer is not None:
            self._main_win_vis_timer.start(0)

    def _main_win_vis_timeout(self) -> None:
        try:
            if self._dock_widget is None or self._suppress_visibility_sync:
                return
            m = qtutils.sessionWindow()
            if m is not None and m.isMinimized():
                return
            # Route through mode_manager so Mu PyMinorMode._active stays in sync
            # with the dock (Python Mode.toggle() only updates Python _active).
            if not self._dock_widget.isVisible() and self._active:
                commands.sendInternalEvent("mode-manager-toggle-mode", "session_manager")
            elif self._dock_widget.isVisible() and not self._active:
                commands.sendInternalEvent("mode-manager-toggle-mode", "session_manager")
        except Exception:
            pass
