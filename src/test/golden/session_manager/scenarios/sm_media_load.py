"""Scenario: real media load + full preview quiesce, no other interaction
(COVERAGE §H, items H1/H2/H5 -- previously "Dropped" as non-deterministic).

Loads a real JPEG and a real movie (not `movieproc`, which never exercises
the real-file loading or local_thumbnail_gen/rvio preview pipeline), waits
for progressive loading AND both real thumbnail and filmstrip previews to
be on disk for every source, and does nothing else before capturing. This
is the fix for the previously-dropped nondeterminism: rather than a
best-effort growing sleep, `_sm_common.quiesce_real_previews` polls the
exact paths session_manager itself treats as "preview ready" and raises
loudly on timeout instead of capturing an unquiesced, nondeterministic
panel.

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


# --- 1. Load real media, wait for progressive loading to finish ---------------
source_nodes, group_nodes = sm.add_real_sources(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE], log=log
)
log("nodes:", rvc.nodes())

# --- 2. Open the panel so local_thumbnail_gen starts generating previews ------
panel = sm.open_session_manager_panel(log=log)

# --- 3. Quiesce: wait for a REAL thumbnail + filmstrip for every source ------
sm.quiesce_real_previews(source_nodes, log=log)
sm.assert_preview_paths_ready(source_nodes, log=log)

# --- 4. Behavioral capture -----------------------------------------------------
rvc.saveSession(os.path.join(out_dir, "session.rv"), True, False, False)
log("saved session.rv")

# --- 5. Pixel capture (now deterministic: previews are fully arrived) --------
ok, w, h = grab_widget_png(panel, os.path.join(out_dir, "panel.png"))
log("panel.png saved:", ok, "size", w, "x", h)

diag.close()
