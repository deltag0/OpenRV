#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Node tree model and drag-and-drop view for the session manager."""

from __future__ import annotations

import io
import sys
from collections.abc import Callable

from rv import commands

try:
    from PySide6.QtCore import QMimeData, QModelIndex, Qt, QTimer, QUrl
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QStandardItem, QStandardItemModel
    from PySide6.QtWidgets import QTreeView
except ImportError:  # pragma: no cover - Qt5 builds
    from PySide2.QtCore import QMimeData, QModelIndex, Qt, QTimer, QUrl
    from PySide2.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QStandardItem, QStandardItemModel
    from PySide2.QtWidgets import QTreeView

from session_manager_support import (
    NotASubComponent,
    USER_ROLE_NODE,
    USER_ROLE_SORT,
    USER_ROLE_SUBTYPE,
    index_of,
    item_is_sub_component,
    item_node,
    node_from_index,
    set_property,
    set_sort_key_in_parent,
)

_SORT_TIMER_MS = 200 if sys.platform == "win32" else 100


def _drag_event_pos(event: QDragMoveEvent):
    if hasattr(event, "position"):
        return event.position().toPoint()
    return event.pos()


def _map_items(
    model: QStandardItemModel,
    predicate: Callable[[QStandardItem], bool],
    root: QStandardItem | None = None,
) -> list[QStandardItem]:
    matched: list[QStandardItem] = []

    def walk(item: QStandardItem) -> None:
        for row in range(item.rowCount()):
            child = item.child(row, 0)
            if child is not None:
                walk(child)
        if item_node(item) != "" and predicate(item):
            matched.append(item)

    if root is None:
        for row in range(model.rowCount()):
            item = model.item(row, 0)
            if item is not None:
                walk(item)
    else:
        walk(root)

    return matched


def _item_of_node(model: QStandardItemModel, node: str) -> QStandardItem | None:
    items = _map_items(
        model,
        lambda item: item_node(item) == node and not item_is_sub_component(item),
    )
    return items[0] if items else None


def _assign_sort_order(root: QStandardItem | None) -> None:
    if root is None:
        return
    try:
        root_node = item_node(root)
        index = 0
        for row in range(root.rowCount()):
            item = root.child(row, 0)
            if item is None:
                continue
            node = item_node(item)
            set_sort_key_in_parent(node, root_node, index)
            index += 1
    except Exception as exc:
        print("CAUGHT %s\n" % exc)


class NodeModel(QStandardItemModel):
    def mimeTypes(self) -> list[str]:
        types = list(super().mimeTypes())
        types.append("text/uri-list")
        types.append("text/plain")
        return types

    def mimeData(self, indices: list[QModelIndex]) -> QMimeData | None:
        mime_data = super().mimeData(indices)
        if mime_data is None:
            return mime_data

        urls: list[QUrl] = []
        text = io.StringIO()

        try:
            rvid = "%s@%s:%s" % (
                commands.remoteLocalContactName(),
                commands.myNetworkHost(),
                commands.myNetworkPort(),
            )

            for index in indices:
                node = node_from_index(index, self)
                ntype = commands.nodeType(node)

                if ntype == "RVSourceGroup":
                    media = commands.getStringProperty("%s_source.media.movie" % node)
                    text.write("RVFileSource %s.media.movie = %s\n" % (node, media))
                    for movie in media:
                        urls.append(
                            QUrl("rvnode://%s/%s/%s/%s" % (rvid, ntype, node, movie))
                        )
                else:
                    text.write("%s %s\n" % (ntype, node))
                    urls.append(QUrl("rvnode://%s/%s/%s" % (rvid, ntype, node)))

            mime_data.setText(text.getvalue())
            mime_data.setUrls(urls)
        except Exception as exc:
            print("CAUGHT %s\n" % exc)

        return mime_data


class NodeTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drop_action = Qt.IgnoreAction
        self._dragged_node_paths: list[list[str]] | None = None
        self._dragging_non_folders = False
        self._view_model: QStandardItemModel | None = None
        self._sort_folders: list[str] = []
        self._sort_timer = QTimer(self)
        self._sort_timer.setSingleShot(True)
        self._sort_timer.timeout.connect(self._sort_folders_cb)
        self._folders_item: QStandardItem | None = None

    def sortFolderChildren(self, folder: str) -> None:
        if commands.nodeType(folder) != "RVFolderGroup":
            return
        if folder not in self._sort_folders:
            self._sort_folders.append(folder)

    def selectedNodePaths(self) -> list[list[str]]:
        paths: list[list[str]] = []
        for index in self.selectionModel().selectedIndexes():
            if index.column() != 0:
                continue

            path: list[str] = []
            current = index
            while current.isValid():
                item = self._view_model.itemFromIndex(current) if self._view_model else None
                path.append(item_node(item))
                current = current.parent()
            paths.append(path)

        return paths

    def filteredDraggedPaths(
        self, predicate: Callable[[list[str]], bool]
    ) -> list[list[str]]:
        if self._dragged_node_paths is None:
            return []
        return [path for path in self._dragged_node_paths if predicate(path)]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        source_widget = event.source()
        mime_data = event.mimeData()

        if source_widget is self:
            self._dragged_node_paths = self.selectedNodePaths()
            self._dragging_non_folders = False

            for path in self._dragged_node_paths:
                if commands.nodeExists(path[0]) and commands.nodeType(path[0]) != "RVFolderGroup":
                    self._dragging_non_folders = True

            if self._folders_item is not None:
                if self._dragging_non_folders:
                    self._folders_item.setFlags(Qt.ItemIsEnabled)
                else:
                    self._folders_item.setFlags(Qt.ItemIsDropEnabled | Qt.ItemIsEnabled)

            super().dragEnterEvent(event)
        elif source_widget is not None:
            return
        else:
            print("No like source: %s\n" % source_widget)
            for fmt in mime_data.formats():
                print("%s\n" % fmt)

            if mime_data.hasUrls():
                for url in mime_data.urls():
                    print("%s\n" % url.toString(QUrl.None_))

            if mime_data.hasText():
                print("%s\n" % mime_data.text())

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._view_model is None:
            event.ignore()
            return

        index = self.indexAt(_drag_event_pos(event))
        item = self._view_model.itemFromIndex(index)
        if item is None:
            event.ignore()
            return

        node = item_node(item)
        if index.column() != 0:
            event.ignore()
            return

        if event.dropAction() == Qt.CopyAction and commands.nodeExists(node):
            outs = commands.nodeConnections(node)[1]
            ntype = commands.nodeType(node)

            if self._dragged_node_paths is not None:
                for path in self._dragged_node_paths:
                    if len(path) > 1 and commands.nodeExists(path[1]):
                        if ntype != "RVFolderGroup":
                            for out in outs:
                                if out == path[1]:
                                    event.ignore()
                                    return

                        if path[1] == node:
                            event.ignore()
                            return

        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._drop_action = event.dropAction()
        super().dropEvent(event)
        self._dragged_node_paths = None
        self._drop_action = Qt.IgnoreAction
        self._sort_timer.start(_SORT_TIMER_MS)

    def _sort_folders_cb(self) -> None:
        if self._view_model is None:
            self._sort_folders.clear()
            return

        for folder in self._sort_folders:
            item = _item_of_node(self._view_model, folder)
            if item is not None:
                _assign_sort_order(item)

        self._sort_folders.clear()


# Re-export session_manager role constants used by tree wiring.
__all__ = [
    "NodeModel",
    "NodeTreeView",
    "NotASubComponent",
    "USER_ROLE_NODE",
    "USER_ROLE_SORT",
    "USER_ROLE_SUBTYPE",
]
