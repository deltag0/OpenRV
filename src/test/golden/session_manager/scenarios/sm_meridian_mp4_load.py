"""Meridian MP4 load + thumbnail pixel parity vs Mu session_manager.

Uses ``addSources()`` (File→Open path) with a pinned Meridian production clip,
waits for real rvio thumbnail+filmstrip files, and captures:

  * behavioral: ``session.rv`` (media path normalized to ``<MP4_FIXTURE>``)
  * pixel: ``panel.png`` — full Session Manager panel at dmax=0 vs Mu baseline
  * pixel: ``preview.png`` — first source row preview widget only (thumbnail crop)

Requires the Meridian clip on disk — set ``fixtures/mp4.env`` or:

  export SM_TEST_MP4_DIR=$HOME/Downloads/Meridian-PS-Cloth/Meridian-PS-Cloth/Meridian-Cloth-PS-V001
  export SM_TEST_MP4_FIXTURE=$SM_TEST_MP4_DIR/Meridian_-_Clip_0043_SHOTREF.mp4

Mu baseline: ``IMPL=mu RV_MODE_IMPL_session_manager=mu ./capture_golden.sh sm_meridian_mp4_load``
Verify:     ``./run_all_goldens.sh sm_meridian_mp4_load`` (Python port, dmax=0)
"""

import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


mp4 = sm.resolve_meridian_mp4_fixture()
log("meridian mp4:", mp4)
log("SM_TEST_MP4_DIR:", sm.MP4_DIR or "(unset)")

source_nodes, _group_nodes = sm.add_sources_explicit(
    [mp4], log=log, timeout_ms=180000
)
log("nodes:", rvc.nodes())

panel = sm.open_session_manager_panel(log=log)
sm.quiesce_real_previews(source_nodes, timeout_ms=600000, log=log)
sm.assert_preview_paths_ready(source_nodes, log=log)

rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

sm.grab_first_source_preview(panel, os.path.join(out_dir, "preview.png"), log=log)

diag.close()
