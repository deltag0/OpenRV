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
    [--impl mu|python] [--mode MODE[,MODE...]] [--package PKG[,PKG...]]
"""

import argparse
import os
import subprocess
import sys

from runtime_log_check import check_runtime_delta, signatures_from_out_dir

# Repo root = five levels up from this file
#   src/test/golden/harness/run_scenario.py -> <repo>
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
DEFAULT_RV = os.path.join(REPO_ROOT, "_build", "stage", "app", "bin", "rv")
MODE_IMPL_ENV_PREFIX = "RV_MODE_IMPL_"
SESSION_MANAGER_PKG = "session_manager"
# Edit/stack/switch modes ship inside the session_manager package directory.
SESSION_MANAGER_SIBLING_MODES = {
    "Composite_edit_mode",
    "FolderGroup_edit_mode",
    "LayoutGroup_edit_mode",
    "RetimeGroup_edit_mode",
    "SequenceGroup_edit_mode",
    "SourceGroup_edit_mode",
    "Stack_edit_mode",
    "StackGroup_edit_mode",
    "Switch_edit_mode",
    "SwitchGroup_edit_mode",
    "transform_manip",
}
SESSION_MANAGER_ALL_MODES = [SESSION_MANAGER_PKG] + sorted(SESSION_MANAGER_SIBLING_MODES)
LAYER_SELECT_PKG = "layer_select"


def package_dir_for_mode(mode_name: str) -> str | None:
    """Map an RV mode name to its package source directory on PYTHONPATH."""
    direct = os.path.join(REPO_ROOT, "src", "plugins", "rv-packages", mode_name)
    if os.path.isdir(direct):
        return direct
    sm_pkg = os.path.join(REPO_ROOT, "src", "plugins", "rv-packages", SESSION_MANAGER_PKG)
    if mode_name in SESSION_MANAGER_SIBLING_MODES or mode_name == SESSION_MANAGER_PKG:
        if os.path.isdir(sm_pkg):
            return sm_pkg
    return None


def apply_mode_impl(env: dict[str, str], modes: list[str], impl: str) -> None:
    """Set per-mode impl env vars."""
    for name in modes:
        env[f"{MODE_IMPL_ENV_PREFIX}{name}"] = impl


def parse_mode_names(raw: str) -> list[str]:
    return [m.strip() for m in raw.split(",") if m.strip()]


def parse_package_names(raw: str | None, extras: list[str] | None = None) -> list[str]:
    """Comma-separated and/or repeated --package values."""
    names: list[str] = []
    if raw:
        names.extend(parse_mode_names(raw))
    for item in extras or []:
        names.extend(parse_mode_names(item))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def package_dir_for_name(package_name: str) -> str | None:
    """Resolve an rv-packages/ directory name to an absolute source path."""
    pkg = os.path.join(REPO_ROOT, "src", "plugins", "rv-packages", package_name)
    if os.path.isdir(pkg):
        return pkg
    return None


# The in-RV wrapper: exec the scenario file, and ALWAYS hard-exit so a
# windowless RV never hangs waiting for a GUI event. A scenario exception
# exits non-zero so the runner can report failure.
_PYEVAL = (
    "import os, sys, traceback\n"
    "try:\n"
    "    exec(open(os.environ['GOLDEN_BOOTSTRAP']).read(), {'__name__': '__bootstrap__'})\n"
    "except Exception:\n"
    "    traceback.print_exc()\n"
    "try:\n"
    "    exec(open(os.environ['GOLDEN_SCENARIO']).read(), {'__name__': '__scenario__'})\n"
    "    _rc = 0\n"
    "except SystemExit as e:\n"
    "    _rc = int(e.code) if isinstance(e.code, int) else 0\n"
    "except BaseException:\n"
    "    traceback.print_exc()\n"
    "    _rc = 3\n"
    "    try:\n"
    "        with open(os.path.join(os.environ['GOLDEN_OUT'], 'traceback.txt'), 'w') as _f:\n"
    "            traceback.print_exc(file=_f)\n"
    "    except Exception:\n"
    "        pass\n"
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
        "--no-xvfb",
        action="store_true",
        help="Skip the xvfb-run wrapper and launch --rv directly. Not for gated "
        "captures (loses the pinned software-Mesa determinism) -- only for "
        "smoke-testing scenario logic on a platform without Xvfb (e.g. macOS).",
    )
    ap.add_argument(
        "--menu-bar",
        action="store_true",
        help="Do not pass -nomb (keep the menu bar). Required for scenarios that "
        "exercise Tools/… menu items headlessly.",
    )
    ap.add_argument(
        "--impl",
        choices=("mu", "python", "default"),
        default=None,
        help="Implementation for --mode name(s): sets RV_MODE_IMPL_<mode>=<impl> "
        "(omitted: forces mu unless already in the environment, for backward "
        "compatibility with existing gates). 'default' sets nothing at all -- "
        "RV picks its own real, shipped default exactly as a normal launch "
        "would, with no test-harness override. Use this to test the actual "
        "startup/mode-selection logic itself, not a specific implementation -- "
        "see run_gui_sanity_gate.sh's final phase, added 2026-07-24 after a "
        "real bug (session_manager's panel unreachable via its real 'x' "
        "shortcut on a normal launch) was found that every existing gate "
        "missed precisely because they all force an explicit impl.",
    )
    ap.add_argument(
        "--mode",
        default=",".join(SESSION_MANAGER_ALL_MODES),
        help="Comma-separated RV mode name(s) affected by --impl "
        f"(default: all {len(SESSION_MANAGER_ALL_MODES)} session_manager package modes)",
    )
    ap.add_argument(
        "--allow-runtime-errors",
        action="store_true",
        help="Skip runtime-error check (Mu capture / debug only).",
    )
    ap.add_argument(
        "--runtime-golden-dir",
        default=None,
        help="Golden dir with runtime_errors.txt; fail only on NEW errors vs Mu baseline.",
    )
    ap.add_argument(
        "--package",
        action="append",
        default=[],
        help="rv-packages/ directory name(s) to prepend to PYTHONPATH when the package "
        "folder differs from --mode (repeatable; each value may be comma-separated). "
        "Example: --mode layer_select_mode --package layer_select",
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
    env["LIBGL_ALWAYS_SOFTWARE"] = "1"  # force software Mesa (deterministic, no GPU)
    env["PYTHONUNBUFFERED"] = "1"
    # Let harness/package PYTHONPATH precede staged PlugIns/Python so Mu→Python
    # migration edits under src/plugins/rv-packages/ load without rebuild.
    env["RV_PYTHONPATH_APPEND_ONLY"] = "1"
    env["GOLDEN_OUT"] = out  # scenario writes artifacts here
    env["GOLDEN_SCENARIO"] = scenario
    env["GOLDEN_BOOTSTRAP"] = os.path.join(_HERE, "golden_bootstrap.py")
    # Movieproc scenarios pin sRGB2linear=1 via source_setup (immediate mode loads
    # inactive in -pyeval runs). Golden-mac baselines assume this color path.
    env.setdefault("GOLDEN_SOURCE_SETUP", "1")
    mode_names = parse_mode_names(args.mode)
    if args.impl == "default":
        pass  # deliberately set nothing -- see --impl's help text
    elif args.impl is not None:
        apply_mode_impl(env, mode_names, args.impl)
    elif not any(k.startswith(MODE_IMPL_ENV_PREFIX) for k in env):
        apply_mode_impl(env, mode_names, "mu")
    # Always put the session_manager package on PYTHONPATH when any of its modes
    # are selected (edit modes live alongside session_manager.py).
    pkg_dirs: list[str] = []
    sm_pkg = os.path.join(REPO_ROOT, "src", "plugins", "rv-packages", SESSION_MANAGER_PKG)
    if os.path.isdir(sm_pkg) and any(
        n == SESSION_MANAGER_PKG or n in SESSION_MANAGER_SIBLING_MODES for n in mode_names
    ):
        pkg_dirs.append(sm_pkg)
    for name in mode_names:
        pkg_dir = package_dir_for_mode(name)
        if pkg_dir and pkg_dir not in pkg_dirs:
            pkg_dirs.append(pkg_dir)
    for pkg_name in parse_package_names(None, args.package):
        pkg_dir = package_dir_for_name(pkg_name)
        if pkg_dir is None:
            print(f"FAIL: --package {pkg_name!r} not found under rv-packages/", file=sys.stderr)
            return 2
        if pkg_dir not in pkg_dirs:
            pkg_dirs.append(pkg_dir)
    package_names = parse_package_names(None, args.package)
    mu_module_dirs: list[str] = []
    for pkg_dir in pkg_dirs:
        if os.path.isdir(pkg_dir):
            mu_module_dirs.append(pkg_dir)
    stage_mu = os.path.join(REPO_ROOT, "_build", "stage", "app", "PlugIns", "Mu")
    stage_mu_mac = os.path.join(
        REPO_ROOT, "_build", "stage", "app", "RV.app", "Contents", "PlugIns", "Mu"
    )
    for candidate in (stage_mu_mac, stage_mu):
        if os.path.isdir(candidate) and candidate not in mu_module_dirs:
            mu_module_dirs.append(candidate)
    if mu_module_dirs:
        prior_mu = env.get("MU_MODULE_PATH", "")
        env["MU_MODULE_PATH"] = os.pathsep.join(
            mu_module_dirs + ([prior_mu] if prior_mu else [])
        )
    # Scenarios are exec()'d with no __file__, so they can't find sibling
    # modules (_sm_common.py) or the shared harness (qt_scenario_utils.py) on
    # their own -- always put both on PYTHONPATH, not just when pkg_dirs is
    # non-empty.
    scenario_dir = os.path.dirname(scenario)
    prior = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([scenario_dir, _HERE] + pkg_dirs + ([prior] if prior else []))
    # Root/container safety (harmless otherwise).
    env.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    if args.no_xvfb:
        cmd = [args.rv, "-noPrefs", "-pyeval", _PYEVAL]
    else:
        cmd = [
            "xvfb-run",
            "-a",
            "-s",
            f"-screen 0 {args.screen}",
            args.rv,
            "-noPrefs",
            "-pyeval",
            _PYEVAL,
        ]
    if not args.menu_bar:
        # Insert -nomb before -pyeval (deterministic headless default).
        cmd.insert(cmd.index("-pyeval"), "-nomb")
    # Optional rv-packages (e.g. layer_select) are skipped under -noPrefs unless
    # ModeManagerPreload forces registration + load (see rvnuke's rvNuke.py).
    preload_modes = [n for n in mode_names if n not in SESSION_MANAGER_ALL_MODES]
    flag_tokens: list[str] = []
    if preload_modes:
        flag_tokens.append("ModeManagerPreload=" + ",".join(preload_modes))
    if flag_tokens:
        cmd[cmd.index("-pyeval") : cmd.index("-pyeval")] = [
            "-flags",
            *flag_tokens,
        ]
    # env.get(..., "mu") would misreport --impl default as "mu" -- it isn't
    # set to anything; show that honestly instead of implying a value.
    impl_note = ", ".join(
        f"{MODE_IMPL_ENV_PREFIX}{n}={env.get(f'{MODE_IMPL_ENV_PREFIX}{n}', '(unset -- RV default)')}"
        for n in mode_names
    )
    print(
        f"[run_scenario] {os.path.basename(scenario)} -> {out} ({impl_note})",
        file=sys.stderr,
    )
    rv_log_path = os.path.join(out, "rv.log")
    try:
        with open(rv_log_path, "w", encoding="utf-8") as rv_log:
            proc = subprocess.run(
                cmd,
                env=env,
                timeout=args.timeout,
                stdout=rv_log,
                stderr=subprocess.STDOUT,
            )
    except subprocess.TimeoutExpired:
        print(f"FAIL: RV did not finish within {args.timeout}s", file=sys.stderr)
        return 124
    if proc.returncode != 0:
        print(f"FAIL: scenario exited {proc.returncode}", file=sys.stderr)
        return proc.returncode

    if not args.allow_runtime_errors:
        if args.runtime_golden_dir:
            new_errors = check_runtime_delta(out, os.path.abspath(args.runtime_golden_dir))
            if new_errors:
                print(
                    "FAIL: new runtime errors vs Mu golden "
                    "(see rv.log, runtime_errors.txt)",
                    file=sys.stderr,
                )
                for err in new_errors[:5]:
                    print("---", file=sys.stderr)
                    print(err, file=sys.stderr)
                if len(new_errors) > 5:
                    print(f"... and {len(new_errors) - 5} more", file=sys.stderr)
                return 5
        else:
            sigs = signatures_from_out_dir(out)
            if sigs:
                print(
                    "FAIL: runtime errors during scenario "
                    "(pass --runtime-golden-dir for delta check; see rv.log)",
                    file=sys.stderr,
                )
                for sig in sorted(sigs)[:5]:
                    print("---", file=sys.stderr)
                    print(sig, file=sys.stderr)
                return 5

    print("[run_scenario] OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
