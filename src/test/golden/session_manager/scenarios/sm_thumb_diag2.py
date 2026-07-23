import os
import rv.commands as rvc
out_dir = os.environ["GOLDEN_OUT"]
diag = open(os.path.join(out_dir, "diag.txt"), "w")
def log(*a):
    print(*a, file=diag, flush=True)
for name in ("local_thumbnail_gen", "session_manager"):
    try:
        log(name, "isModeActive", rvc.isModeActive(name))
    except Exception as e:
        log(name, "isModeActive err", e)
    try:
        rvc.activateMode(name)
        log(name, "activateMode OK, now active", rvc.isModeActive(name))
    except Exception as e:
        log(name, "activateMode err", e)
try:
    import local_thumbnail_gen as ltg
    log("theMode after activate", ltg.theMode())
except Exception as e:
    log("ltg import", e)
diag.close()
