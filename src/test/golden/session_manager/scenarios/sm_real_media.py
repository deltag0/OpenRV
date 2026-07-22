"""Scenario: session_manager with real file media (EXR + JPEG).

Exercises paths that movieproc-only goldens skip:
  - progressive loading / source-group-complete
  - source row metadata + preview widgets
  - local_thumbnail_gen async previews (best-effort)

Writes $GOLDEN_OUT/diag.txt and session.rv; panel.png if the dock is found.
"""
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
except ImportError:  # pragma: no cover
    from PySide2 import QtWidgets, QtCore


def pump(ms):
    app = QtWidgets.QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)


# Real media bundled with the staged Python runtime (stable paths in CI/dev).
_media_candidates = [
    "/home/vterme/Documents/OpenRV/_build/stage/app/lib/python3.11/test/imghdrdata/python.exr",
    "/home/vterme/Documents/OpenRV/_build/stage/app/lib/python3.11/test/imghdrdata/python.jpg",
    "/home/vterme/Documents/OpenRV/_build/stage/app/plugins/SupportFiles/annotate/hpm_0000_0007_0_img0131.jpg",
]

media_paths = [p for p in _media_candidates if os.path.isfile(p)]
log("media candidates found:", media_paths)

if not media_paths:
    log("ERROR: no real media files on disk — skipping load")
    diag.close()
    raise SystemExit(2)

for path in media_paths:
    try:
        node = rvc.addSourceVerbose([path])
        log("addSource", path, "->", node)
    except Exception as exc:
        log("addSource FAILED", path, exc)

pump(1500)
log("loadTotal:", rvc.loadTotal())
log("nodes:", rvc.nodes())

# Open session manager and let previews/thumbnail gen catch up.
try:
    rvc.sendInternalEvent("key-down--x", "")
except Exception as exc:
    log("key-down--x:", exc)
pump(500)

import session_manager as sm

mode = sm.theMode()
log("theMode:", mode, "active:", getattr(mode, "_active", None) if mode else None)

try:
    import local_thumbnail_gen as ltg
    ltmode = ltg.theMode()
    log("local_thumbnail_gen theMode:", ltmode, "active:", getattr(ltmode, "_active", None) if ltmode else None)
    if ltmode is not None and not ltmode._active:
        try:
            ltmode.toggle()
            log("local_thumbnail_gen toggled active:", ltmode._active)
        except Exception as exc:
            log("local_thumbnail_gen toggle failed:", exc)
except Exception as exc:
    log("local_thumbnail_gen import:", exc)

# Pump through progressive loading + async thumbnail generation (rvio).
for wait_ms in (1000, 2000, 5000, 10000, 15000):
    pump(wait_ms)
    thumbs = {}
    for n in rvc.nodes():
        if not n.endswith("_source"):
            continue
        try:
            thumbs[n] = rvc.sendInternalEvent("session-manager-get-thumbnail-path", n)
        except Exception:
            thumbs[n] = "ERR"
    log(f"after {wait_ms}ms: loadTotal={rvc.loadTotal()} thumbs={thumbs}")
    if all(v for v in thumbs.values()):
        break

log("RV_APP_RVIO:", os.environ.get("RV_APP_RVIO", "<unset>"))

win = qtutils.sessionWindow()
dock = win.findChild(QtWidgets.QDockWidget, "session_manager") if win else None
log("dock visible:", dock.isVisible() if dock else None)

if dock is not None:
    if not dock.isVisible():
        dock.show()
    pump(400)
    pixmap = dock.grab()
    ok = pixmap.save(os.path.join(out_dir, "panel.png"), "PNG")
    log("panel.png saved:", ok, pixmap.width(), "x", pixmap.height())

# Probe preview internal events for each source-like node.
for n in rvc.nodes():
    if not n.endswith("_source"):
        continue
    try:
        thumb = rvc.sendInternalEvent("session-manager-get-thumbnail-path", n)
        strip = rvc.sendInternalEvent("session-manager-get-filmstrip-path", n)
        log("preview paths", n, "thumb=", thumb, "strip=", strip)
    except Exception as exc:
        log("preview probe failed", n, exc)

rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")
diag.close()
