#
# Shared graph / property helpers for the session_manager Python port.
#
# Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
#
from __future__ import annotations

import sys

from rv import commands, extra_commands

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QStandardItem
except ImportError:  # pragma: no cover
    from PySide2.QtCore import Qt
    from PySide2.QtGui import QStandardItem

NotASubComponent = 0
MediaSubComponent = 1
ViewSubComponent = 2
LayerSubComponent = 3
ChannelSubComponent = 4

USER_ROLE_PARENT = Qt.UserRole + 1
USER_ROLE_NODE = Qt.UserRole + 2
USER_ROLE_SORT = Qt.UserRole + 3
USER_ROLE_SUBTYPE = Qt.UserRole + 4
USER_ROLE_SUBVALUE = Qt.UserRole + 5
USER_ROLE_HASH = Qt.UserRole + 6
USER_ROLE_MEDIA = Qt.UserRole + 7


def _contains(values: list[str], value: str) -> bool:
    return value in values


def _remove(values: list[str], value: str) -> list[str]:
    return [v for v in values if v != value]


def source_node_of_group(group: str) -> str | None:
    for node in commands.nodesInGroup(group):
        ntype = commands.nodeType(node)
        if ntype in ("RVFileSource", "RVImageSource"):
            return node
    return None


def item_sub_component_type_for_name(name: str) -> int:
    if name == "view":
        return ViewSubComponent
    if name == "layer":
        return LayerSubComponent
    if name == "channel":
        return ChannelSubComponent
    return NotASubComponent


def item_sub_component_media(item: QStandardItem) -> str:
    data = item.data(USER_ROLE_MEDIA)
    return "" if data is None else str(data)


def item_sub_component_hash(item: QStandardItem) -> str:
    data = item.data(USER_ROLE_HASH)
    return "" if data is None else str(data)


def hashed_sub_component(media: str, view: str | None, layer: str | None) -> str:
    v = "@." if view == "" else view
    l = "@." if layer == "" else layer
    if v is None and l is None:
        return "%s!~!~" % media
    if v is None:
        return "%s!~%s!~" % (media, l)
    if l is None:
        return "%s!~!~%s" % (media, v)
    return "%s!~%s!~%s" % (media, v, l)


def hashed_sub_component_item(item: QStandardItem) -> str:
    value = item_sub_component_value(item)
    sub_type = item_sub_component_type(item)
    parent = item.parent()
    pvalue = item_sub_component_value(parent) if parent is not None else ""

    if sub_type == MediaSubComponent:
        return hashed_sub_component(value, None, None)
    if sub_type == LayerSubComponent and parent is not None:
        grand = parent.parent()
        psub = item_sub_component_type(parent)
        arg0 = item_sub_component_value(grand) if psub == ViewSubComponent and grand else pvalue
        arg1 = pvalue if psub == ViewSubComponent else None
        return hashed_sub_component(arg0, arg1, value)
    if sub_type == ViewSubComponent:
        return hashed_sub_component(pvalue, value, None)
    return ""


def is_sub_component_expanded(node: str, item: QStandardItem) -> bool:
    prop_name = "%s.sm_state.expandedSubState" % node
    key = hashed_sub_component_item(item)
    if commands.propertyExists(prop_name):
        return _contains(list(commands.getStringProperty(prop_name)), key)
    return False


def set_sub_component_expanded(node: str, item: QStandardItem, expanded: bool) -> None:
    prop_name = "%s.sm_state.expandedSubState" % node
    key = hashed_sub_component_item(item)
    if commands.propertyExists(prop_name):
        props = list(commands.getStringProperty(prop_name))
        has_it = _contains(props, key)
        if has_it and not expanded:
            set_property(prop_name, _remove(props, key))
        elif not has_it and expanded:
            props.append(key)
            set_property(prop_name, props)
    elif expanded:
        set_property(prop_name, [key])


def rename_by_type(node: str, inputs: list[str]) -> None:
    import re

    n = len(inputs)
    basename = commands.nodeType(node)
    if re.match(r"^RV", basename):
        basename = basename[2:]
    if basename.endswith("Group"):
        basename = basename[:-5]

    if n == 0:
        name = "Empty %s" % basename
    elif n < 3:
        name = "%s of " % basename
        for i, inp in enumerate(inputs):
            if i > 0:
                name += " "
            if i == n - 1 and n > 1:
                name += "and "
            name += extra_commands.uiName(inp)
    else:
        name = "%s of %d views " % (basename, n)

    commands.setUIName(node, name)


def set_node_request(source_node: str, value: list[str]) -> None:
    prop = source_node + ".request.imageComponent"
    if commands.propertyExists(prop):
        commands.setStringProperty(prop, value, True)
    else:
        set_property(prop, value)


def component_and_folder_node_from_hash(hash_value: str, node: str) -> tuple[str | None, str | None]:
    folder = None
    component_node = None
    for n in commands.nodes():
        if commands.nodeType(n) == "RVSourceGroup" and component_node is None:
            prop_name = n + ".sm_state.componentHash"
            if commands.propertyExists(prop_name):
                try:
                    prop = commands.getStringProperty(prop_name)
                    parent = commands.getStringProperty(n + ".sm_state.componentOfNode")
                    if prop and prop[0] == hash_value and parent and parent[0] == node:
                        component_node = n
                except Exception:
                    pass
        elif commands.nodeType(n) == "RVFolderGroup":
            pname = n + ".sm_state.componentFolderOfNode"
            if commands.propertyExists(pname):
                try:
                    prop = commands.getStringProperty(pname)
                    if prop and prop[0] == node:
                        folder = n
                except Exception:
                    pass
    return component_node, folder


def new_sub_component_node(
    hash_value: str,
    sub_type: int,
    filename: str,
    full_name: str,
    comp_prop_value: list[str],
    node: str,
    folder: str | None,
) -> str:
    sources = commands.addSourceVerbose([filename])
    if not sources:
        raise RuntimeError("addSourceVerbose failed for %s" % filename)
    source_node = sources[0] if isinstance(sources, list) else sources
    node_name = extra_commands.uiName(node)
    group_node = commands.nodeGroup(source_node)
    display_name = "default" if full_name == "" else full_name

    if folder is None:
        folder = commands.newNode("RVFolderGroup", "%s_components" % node)
        commands.setUIName(folder, "Components of %s" % extra_commands.uiName(node))
        set_property(folder + ".sm_state.componentFolderOfNode", node)
        set_property("%s.sm_state.expandState" % folder, [])

    inputs = node_inputs(folder)
    inputs.append(group_node)
    commands.setNodeInputs(folder, inputs)

    set_property(group_node + ".sm_state.componentOfNode", node)
    set_property(group_node + ".sm_state.componentHash", hash_value)
    set_property(group_node + ".sm_state.componentSubType", sub_type)

    if sub_type == MediaSubComponent:
        commands.setUIName(group_node, "%s (Media %s)" % (node_name, display_name))
    elif sub_type == ViewSubComponent:
        commands.setUIName(group_node, "%s (View %s)" % (node_name, display_name))
        set_node_request(source_node, comp_prop_value)
    elif sub_type == LayerSubComponent:
        commands.setUIName(group_node, "%s (Layer %s)" % (node_name, display_name))
        set_node_request(source_node, comp_prop_value)
    elif sub_type == ChannelSubComponent:
        commands.setUIName(group_node, "%s (Channel %s)" % (node_name, display_name))
        set_node_request(source_node, comp_prop_value)

    try:
        extra_commands.displayFeedback("NOTE: Created %s" % extra_commands.uiName(group_node), 5)
    except Exception:
        pass
    return group_node


def source_from_sub_component(item: QStandardItem, node: str) -> str:
    hash_value = item_sub_component_hash(item)
    component_node, folder = component_and_folder_node_from_hash(hash_value, node)
    if component_node is not None:
        return component_node

    media_item = None
    view_item = None
    layer_item = None
    current = item
    while current is not None and item_sub_component_type(current) != NotASubComponent:
        stype = item_sub_component_type(current)
        if stype == MediaSubComponent:
            media_item = current
            break
        if stype == LayerSubComponent:
            layer_item = current
        if stype == ViewSubComponent:
            view_item = current
        current = current.parent()

    sub_type = item_sub_component_type(item)
    filename = item_sub_component_value(media_item) if media_item is not None else ""
    full_name = item_sub_component_value(item)
    return new_sub_component_node(
        hash_value,
        sub_type,
        filename,
        full_name,
        sub_component_prop_value(item),
        node,
        folder,
    )


def set_property(prop_name: str, value) -> None:
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
        if not commands.propertyExists(prop_name):
            if value and isinstance(value[0], (int, float)):
                ptype = commands.IntType if all(isinstance(v, int) for v in value) else commands.FloatType
            else:
                ptype = commands.StringType
            commands.newProperty(prop_name, ptype, max(len(value), 1))
        if value and isinstance(value[0], (int, float)):
            if all(isinstance(v, int) for v in value):
                commands.setIntProperty(prop_name, value, True)
            else:
                commands.setFloatProperty(prop_name, [float(v) for v in value], True)
        else:
            commands.setStringProperty(prop_name, value, True)


def set_tool_tip_prop(node: str, tool_tip: str) -> None:
    set_property("%s.sm_state.toolTip" % node, tool_tip)


def node_inputs(node: str) -> list[str]:
    return list(commands.nodeConnections(node, False)[0])


def set_inputs(node: str, inputs: list[str]) -> bool:
    try:
        commands.setNodeInputs(node, inputs)
        return True
    except Exception as exc:
        print("setInputs failed: %s\n" % exc)
        return False


def remove_input(node: str, input_node: str) -> bool:
    if not node:
        return True
    ins = node_inputs(node)
    return set_inputs(node, [n for n in ins if n != input_node])


def has_input(node: str, input_node: str) -> bool:
    if not node:
        return True
    return input_node in node_inputs(node)


def add_input(node: str, input_node: str) -> bool:
    if not commands.nodeExists(node):
        return True
    ins = node_inputs(node)
    if input_node in ins:
        return True
    ins.append(input_node)
    return set_inputs(node, ins)


def contents_equal(a: list, b: list) -> bool:
    return list(a) == list(b)


def is_image_request_prop_equal(name: str, array: list) -> bool:
    prop = "#RVSource.request." + name
    if not commands.propertyExists(prop):
        return not array
    try:
        return contents_equal(commands.getStringProperty(prop), array)
    except Exception:
        return False


def set_image_request_prop(name: str, array: list) -> None:
    prop = "#RVSource.request." + name
    if not is_image_request_prop_equal(name, array):
        set_property(prop, array)
        extra_commands.reload()


def set_image_request(value: list, toggle: bool = True) -> None:
    name = "imageComponent"
    if toggle and is_image_request_prop_equal(name, value):
        set_image_request_prop(name, [])
    else:
        set_image_request_prop(name, value)


def item_node(item: QStandardItem | None) -> str:
    if item is None:
        return ""
    data = item.data(USER_ROLE_NODE)
    return "" if data is None else str(data)


def item_sub_component_type(item: QStandardItem) -> int:
    data = item.data(USER_ROLE_SUBTYPE)
    if data is None:
        return NotASubComponent
    try:
        return int(data)
    except (TypeError, ValueError):
        return NotASubComponent


def item_is_sub_component(item: QStandardItem) -> bool:
    return item_sub_component_type(item) != NotASubComponent


def item_sub_component_value(item: QStandardItem) -> str:
    data = item.data(USER_ROLE_SUBVALUE)
    return "" if data is None else str(data)


def item_parent_node(item: QStandardItem) -> str:
    data = item.data(USER_ROLE_PARENT)
    return "" if data is None else str(data)


def sub_component_prop_value(item: QStandardItem) -> list:
    stype = item_sub_component_type(item)
    if stype == MediaSubComponent:
        return []
    if stype == ViewSubComponent:
        return ["view", item_sub_component_value(item)]
    if stype == LayerSubComponent:
        parent = item.parent()
        view_name = ""
        if parent is not None and item_sub_component_type(parent) == ViewSubComponent:
            view_name = item_sub_component_value(parent)
        return ["layer", view_name, item_sub_component_value(item)]
    if stype == ChannelSubComponent:
        parent = item.parent()
        pval = sub_component_prop_value(parent) if parent is not None else []
        value = item_sub_component_value(item)
        if len(pval) == 0:
            return ["channel", "", "", value]
        if len(pval) == 2:
            return ["channel", pval[1], "", value]
        if len(pval) == 3:
            return ["channel", pval[1], pval[2], value]
    return []


def index_of(values: list[str], value: str) -> int:
    try:
        return values.index(value)
    except ValueError:
        return -1


def node_from_index(index, model) -> str:
    item = model.itemFromIndex(index)
    return item_node(item)


def set_sort_key_in_parent(node: str, parent: str, value: int) -> None:
    prop_parent = "%s.sm_state.sortKeyParent" % node
    prop_key = "%s.sm_state.sortKey" % node
    undefined = sys.maxsize - 100
    del undefined
    if commands.propertyExists(prop_parent) and commands.propertyExists(prop_key):
        try:
            parents = list(commands.getStringProperty(prop_parent))
            keys = list(commands.getIntProperty(prop_key))
            idx = index_of(parents, parent)
            if len(parents) == len(keys):
                if idx == -1:
                    parents.append(parent)
                    keys.append(value)
                    set_property(prop_parent, parents)
                    set_property(prop_key, keys)
                else:
                    keys[idx] = value
                    set_property(prop_key, keys)
                return
        except Exception:
            pass
    set_property(prop_parent, parent)
    set_property(prop_key, value)
