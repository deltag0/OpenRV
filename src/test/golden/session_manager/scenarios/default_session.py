"""Scenario: capture the default (empty) RV session graph.

Runs inside RV (via run_scenario.py -> -pyeval). The `rv.commands` module and a
default session already exist at this point. We dump the full node graph to a
text-GTO session file under $GOLDEN_OUT. This is the simplest possible golden:
no media, no packages driven -- it exercises the launch + capture pipeline and
gives us a determinism baseline.

Artifacts written:
    $GOLDEN_OUT/session.rv   -- full text-GTO node-graph dump (sparse=False)
"""

import os

import rv.commands as rvc

out_dir = os.environ["GOLDEN_OUT"]
session_path = os.path.join(out_dir, "session.rv")

# saveSession(fileName, asCopy, compressed, sparse)
#   asCopy=True     -> do not mark the session's own filename/dirty state
#   compressed=False-> text GTO (diffable, no timestamp in header)
#   sparse=False    -> write ALL persistent properties, not just changed ones
#                      (stable full snapshot; see RV_COMPLETE_SESSION_FILES)
rvc.saveSession(session_path, True, False, False)
