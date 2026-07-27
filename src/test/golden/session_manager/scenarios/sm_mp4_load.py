"""Scenario: load one real MP4 + full preview quiesce (COVERAGE §H).

Uses ``_sm_common.resolve_mp4_fixture()`` so the clip comes from, in order:
  * ``SM_TEST_MP4_FIXTURE`` (single file)
  * first ``*.mp4`` under ``SM_TEST_MP4_DIR``
  * committed ``fixtures/bars_clip.mp4`` (via ``SM_TEST_MOVIE_FIXTURE``)

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


mp4 = sm.resolve_mp4_fixture()
log("mp4 fixture:", mp4)
log("SM_TEST_MP4_DIR:", sm.MP4_DIR or "(unset)")

source_nodes, group_nodes = sm.add_real_sources([mp4], log=log, timeout_ms=120000)
log("nodes:", rvc.nodes())

sm.quiesce_real_previews(source_nodes, timeout_ms=120000, log=log)
sm.assert_preview_paths_ready(source_nodes, log=log)

panel = sm.open_session_manager_panel(log=log)

rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

sm.grab_first_source_preview(panel, os.path.join(out_dir, "preview.png"), log=log)

diag.close()
