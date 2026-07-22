//
// Mu API bridge to the Python session_manager package.
//
// External Mu modes (maya_tools, rvnuke) require this module instead of the
// former session_manager.mu mode implementation.
//
// Copyright (C) 2026  Autodesk, Inc. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0
//
module: session_manager_api
{
    require python;
    require commands;

    class: SessionManagerProxy
    {
        method: selectedNodes (string[];)
        {
            return selectedNodes();
        }
    }

    SessionManagerProxy _proxy;

    \: _pythonModule (python.PyObject;)
    {
        return python.PyImport_Import("session_manager");
    }

    \: _pythonReady (bool;)
    {
        let pymod = _pythonModule();
        if (python.is_nil(pymod)) return false;

        let attr = python.PyObject_GetAttr(pymod, "sessionManagerReady");
        let result = python.PyObject_CallObject(attr, python.PyTuple_New(0));
        if (python.is_nil(result)) return false;
        return python.to_bool(result);
    }

    \: theMode (SessionManagerProxy;)
    {
        if (!_pythonReady()) return nil;
        return _proxy;
    }

    \: selectedNodes (string[];)
    {
        let pymod = _pythonModule();
        if (python.is_nil(pymod)) return string[]();

        let attr = python.PyObject_GetAttr(pymod, "selectedNodesExport");
        let result = python.PyObject_CallObject(attr, python.PyTuple_New(0));
        if (python.is_nil(result)) return string[]();

        string text = python.to_string(result);
        if (text == "") return string[]();
        return text.split("\n");
    }

    \: setToolTipProp (void; string node, string toolTip)
    {
        let pymod = _pythonModule();
        if (python.is_nil(pymod)) return;

        let func = python.PyObject_GetAttr(pymod, "setToolTipProp");
        python.PyObject_CallObject2(func, (node, toolTip));
    }
}
