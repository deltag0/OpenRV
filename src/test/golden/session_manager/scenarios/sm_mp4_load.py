"""Diagnostic: load MP4 and exercise session_manager."""
from __future__ import annotations

import os
import time

import rv.commands as rvc
import rv.qtutils as qtutils

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore


def pump(ms):
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


candidates = [
    os.environ.get("SM_TEST_MP4", ""),
    "/home/vterme/Documents/OpenRV/_build/RV_DEPS_FFMPEG/src/tests/ref/lavf-fate/h264.mp4",
    "/home/vterme/Downloads/Meridian-PS-Cloth/Meridian-PS-Cloth/Meridian-Cloth-PS-V001/Meridian_-_Clip_0043_SHOTREF.mp4",
]
mp4 = next((p for p in candidates if p and os.path.isfile(p)), None)
log("mp4:", mp4)
if mp4 is None:
    log("ERROR: no mp4 file found")
    diag.close()
    raise SystemExit(2)

try:
    node = rvc.addSourceVerbose([mp4])
    log("addSourceVerbose OK:", node)
except Exception as exc:
    log("addSourceVerbose FAILED:", type(exc).__name__, exc)
    diag.close()
    raise SystemExit(1)

pump(3000)
log("loadTotal:", rvc.loadTotal())
log("viewNode:", rvc.viewNode())
log("nodes with source:", [n for n in rvc.nodes() if "sourceGroup" in n and n.endswith("_source")])

try:
    info = rvc.sourceMediaInfo(node)
    log("sourceMediaInfo:", dict(info) if info else None)
except Exception as exc:
    log("sourceMediaInfo FAILED:", exc)

try:
    movie = rvc.getStringProperty(f"{node}.media.movie")
    log("media.movie:", movie)
except Exception as exc:
    log("media.movie FAILED:", exc)

# session manager
try:
    rvc.sendInternalEvent("key-down--x", "")
except Exception as exc:
    log("toggle SM:", exc)
pump(800)

import session_manager as sm
log("session_manager active:", getattr(sm.theMode(), "_active", None) if sm.theMode() else None)

try:
    import local_thumbnail_gen as ltg
    m = ltg.theMode()
    if m and not m._active:
        m.toggle()
    pump(2000)
    thumb = rvc.sendInternalEvent("session-manager-get-thumbnail-path", node)
    strip = rvc.sendInternalEvent("session-manager-get-filmstrip-path", node)
    log("preview thumb:", thumb)
    log("preview strip:", strip)
except Exception as exc:
    log("thumbnail gen:", exc)

try:
    rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
    log("session saved")
except Exception as exc:
    log("saveSession FAILED:", exc)

diag.close()
