"""Diagnostic: thumbnail pipeline without golden_bootstrap force-activation."""
import os

import rv.commands as rvc

import _sm_common as sm
from qt_scenario_utils import pump

out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")


def log(*a):
    print(*a, file=diag, flush=True)


log("GOLDEN_THUMBNAIL_GEN=", os.environ.get("GOLDEN_THUMBNAIL_GEN", "(unset)"))
log("RV_APP_RVIO=", os.environ.get("RV_APP_RVIO", "(unset)"))

try:
    import local_thumbnail_gen as ltg

    m = ltg.theMode()
    log(
        "ltg theMode=",
        m,
        "_active=",
        getattr(m, "_active", None) if m else None,
        "_display_preview=",
        getattr(m, "_display_preview", None) if m else None,
    )
except Exception as e:
    log("ltg err", e)

source_nodes, _ = sm.add_sources_explicit(
    [sm.IMAGE_FIXTURE, sm.MOVIE_FIXTURE], log=log, timeout_ms=120000
)
panel = sm.open_session_manager_panel(log=log)
pump(500)

for sn in source_nodes:
    thumb = rvc.sendInternalEvent("session-manager-get-thumbnail-path", sn)
    log("immediate probe", sn, thumb, os.path.isfile(thumb) if thumb else False)

try:
    sm.quiesce_real_previews(source_nodes, timeout_ms=90000, log=log)
except Exception as e:
    log("quiesce FAIL", e)
    diag.close()
    raise SystemExit(1)

diag.close()
