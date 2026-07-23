"""Scenario: load real media via addSources() (File→Open / drag-drop path).

Unlike ``sm_media_load`` (``addSourceVerbose``), this uses the same progressive
loading pipeline interactive RV uses: ``addSources(..., "explicit", ...)`` plus
``waitForProgressiveLoading()``.

Captures BOTH gates:
  * behavioral: full node-graph text-GTO dump  -> $GOLDEN_OUT/session.rv
  * pixel:      the session_manager panel PNG   -> $GOLDEN_OUT/panel.png
"""

import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


source_nodes, group_nodes = sm.add_sources_explicit(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE], log=log, timeout_ms=120000
)
log("nodes:", rvc.nodes())

panel = sm.open_session_manager_panel(log=log)
sm.quiesce_real_previews(source_nodes, log=log, timeout_ms=120000)
sm.assert_preview_paths_ready(source_nodes, log=log)

rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
