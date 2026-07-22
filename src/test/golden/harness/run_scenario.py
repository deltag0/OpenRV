#!/usr/bin/env python3
"""Outer runner for golden tests.

Launches the real RV application headless (Xvfb + software Mesa), executes an
in-process *scenario* (a Python file run inside RV via ``-pyeval`` with the
``rv.commands`` API available), and collects the artifacts the scenario writes
into an output directory.

Why it is shaped this way (all learned empirically on 2026-07-21):
  * RV needs an OpenGL/GLX context at startup; ``QT_QPA_PLATFORM=offscreen``
    segfaults, so we run under ``xvfb-run`` with ``LIBGL_ALWAYS_SOFTWARE=1``
    (software Mesa / llvmpipe) which is also deterministic for the pixel gate.
  * RV redirects stdout to its own log, so scenarios must write results to
    explicit files under ``$GOLDEN_OUT`` rather than printing them.
  * ``close()`` does not quit a windowless app, so the scenario must end the
    process itself; this runner wraps every scenario so it always ``os._exit``s.

Usage:
    run_scenario.py --scenario PATH --out DIR [--rv PATH] [--timeout N]
    [--impl mu|python] [--mode MODE[,MODE...]]
"""

import argparse
import os
import subprocess
import sys

# Repo root = five levels up from this file
#   src/test/golden/harness/run_scenario.py -> <repo>
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
DEFAULT_RV = os.path.join(REPO_ROOT, "_build", "stage", "app", "bin", "rv")
MODE_IMPL_ENV_PREFIX = "RV_MODE_IMPL_"


def apply_mode_impl(env: dict[str, str], modes: list[str], impl: str) -> None:
    """Set per-mode impl env vars."""
    for name in modes:
        env[f"{MODE_IMPL_ENV_PREFIX}{name}"] = impl


def parse_mode_names(raw: str) -> list[str]:
    return [m.strip() for m in raw.split(",") if m.strip()]

# The in-RV wrapper: exec the scenario file, and ALWAYS hard-exit so a
# windowless RV never hangs waiting for a GUI event. A scenario exception
# exits non-zero so the runner can report failure.
_PYEVAL = (
    "import os, sys, traceback\n"
    "try:\n"
    "    exec(open(os.environ['GOLDEN_SCENARIO']).read(), {'__name__': '__scenario__'})\n"
    "    _rc = 0\n"
    "except SystemExit as e:\n"
    "    _rc = int(e.code) if isinstance(e.code, int) else 0\n"
    "except BaseException:\n"
    "    traceback.print_exc()\n"
    "    _rc = 3\n"
    "sys.stdout.flush(); sys.stderr.flush()\n"
    "os._exit(_rc)\n"
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", required=True, help="Path to the in-RV scenario .py")
    ap.add_argument("--out", required=True, help="Output dir for captured artifacts")
    ap.add_argument("--rv", default=DEFAULT_RV, help="Path to the rv launcher")
    ap.add_argument("--timeout", type=int, default=180, help="Seconds before giving up")
    ap.add_argument("--screen", default="1280x1024x24", help="Xvfb screen geometry")
    ap.add_argument(
        "--impl",
        choices=("mu", "python"),
        default=None,
        help="Implementation for --mode name(s): sets RV_MODE_IMPL_<mode>=<impl> "
        "(default mu unless already in the environment)",
    )
    ap.add_argument(
        "--mode",
        default="session_manager",
        help="Comma-separated RV mode name(s) affected by --impl "
        "(default session_manager)",
    )
    args = ap.parse_args()

    scenario = os.path.abspath(args.scenario)
    out = os.path.abspath(args.out)
    if not os.path.isfile(scenario):
        print(f"FAIL: scenario not found: {scenario}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.rv):
        print(f"FAIL: rv binary not found: {args.rv}", file=sys.stderr)
        return 2
    os.makedirs(out, exist_ok=True)

    env = dict(os.environ)
    env["LIBGL_ALWAYS_SOFTWARE"] = "1"   # force software Mesa (deterministic, no GPU)
    env["PYTHONUNBUFFERED"] = "1"
    env["GOLDEN_OUT"] = out              # scenario writes artifacts here
    env["GOLDEN_SCENARIO"] = scenario
    mode_names = parse_mode_names(args.mode)
    if args.impl is not None:
        apply_mode_impl(env, mode_names, args.impl)
    elif not any(k.startswith(MODE_IMPL_ENV_PREFIX) for k in env):
        apply_mode_impl(env, mode_names, "mu")
    # Make the LIVE package source importable so a Python port loads without a
    # rebuild/stage step (RV imports the mode by bare name via PyImport_Import).
    # A package dir is src/plugins/rv-packages/<modeName>/ that actually exists.
    pkg_dirs = [
        os.path.join(REPO_ROOT, "src", "plugins", "rv-packages", n)
        for n in mode_names
    ]
    pkg_dirs = [d for d in pkg_dirs if os.path.isdir(d)]
    if pkg_dirs:
        prior = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(pkg_dirs + ([prior] if prior else []))
    # Root/container safety (harmless otherwise).
    env.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    cmd = [
        "xvfb-run", "-a", "-s", f"-screen 0 {args.screen}",
        args.rv, "-noPrefs", "-nomb", "-pyeval", _PYEVAL,
    ]
    impl_note = ", ".join(
        f"{MODE_IMPL_ENV_PREFIX}{n}={env.get(f'{MODE_IMPL_ENV_PREFIX}{n}', 'mu')}"
        for n in mode_names
    )
    print(
        f"[run_scenario] {os.path.basename(scenario)} -> {out} ({impl_note})",
        file=sys.stderr,
    )
    try:
        proc = subprocess.run(cmd, env=env, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(f"FAIL: RV did not finish within {args.timeout}s", file=sys.stderr)
        return 124
    if proc.returncode != 0:
        print(f"FAIL: scenario exited {proc.returncode}", file=sys.stderr)
        return proc.returncode
    print("[run_scenario] OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
