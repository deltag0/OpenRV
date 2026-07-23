"""Integration: load every MP4 under SM_TEST_MP4_DIR.

This is an integration/diagnostic scenario, not a golden baseline -- large
production clip sets are too environment-specific for committed
``golden/<id>/`` comparison.  Run via ``fixtures/run_mp4_integration.sh``
(after setting ``SM_TEST_MP4_DIR`` or ``fixtures/mp4.env``).

Writes $GOLDEN_OUT/diag.txt and session.rv; panel.png if the dock is found.
Set SM_TEST_MP4_QUIESCE=1 to wait for thumbnail+filmstrip on every clip
(slow).
"""

import os
import sys

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import grab_widget_png

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


if not sm.MP4_DIR:
    log("ERROR: SM_TEST_MP4_DIR is not set")
    log("  export SM_TEST_MP4_DIR=/path/to/mp4/clips")
    log("  or: cp fixtures/mp4.env.example fixtures/mp4.env && edit")
    diag.close()
    sys.exit(2)

clips = sm.resolve_mp4_clips()
log("SM_TEST_MP4_DIR:", sm.MP4_DIR)
log("clip count:", len(clips))
for path in clips:
    log(" clip:", os.path.basename(path))

source_nodes, group_nodes = sm.add_mp4_clips_sequential(
    clips,
    log=log,
    timeout_ms_per_clip=180000,
)

expected_groups = len(clips)
actual_groups = [n for n in rvc.nodes() if rvc.nodeType(n) == "RVSourceGroup"]
log("RVSourceGroup count:", len(actual_groups), "expected:", expected_groups)
if len(actual_groups) != expected_groups:
    raise RuntimeError(
        "source group count mismatch: got %d expected %d"
        % (len(actual_groups), expected_groups)
    )

panel = sm.open_session_manager_panel(log=log)

if sm.MP4_QUIESCE:
    log("SM_TEST_MP4_QUIESCE=1: waiting for previews on all clips...")
    sm.quiesce_real_previews(
        source_nodes,
        timeout_ms=max(600000, 15000 * len(source_nodes)),
        log=log,
    )
else:
    log("preview quiesce skipped (set SM_TEST_MP4_QUIESCE=1 to enable)")

rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
