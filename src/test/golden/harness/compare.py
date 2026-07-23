#!/usr/bin/env python3
"""Comparators for golden tests: behavioral (GTO node graph) and pixel (PNG).

Behavioral gate:
    Normalize a captured text-GTO session and compare it byte-for-byte against
    the stored golden. Normalization removes environment-specific noise (absolute
    paths, a few volatile session-header fields) so the same graph compares equal
    across machines/checkouts. The default (empty) session is already
    byte-identical run-to-run, so normalization is a no-op there; the hooks exist
    for later media-bearing scenarios.

Pixel gate:
    Thin wrapper over the built `rmsImageDiff -cmp -dmax <v>` tool (whole-image,
    no ROI). Gate at 0 (exact) on the pinned Xvfb + software-Mesa path.

CLI:
    compare.py --golden-dir DIR --actual-dir DIR [--dmax 0]
Expects `session.rv` in each dir; compares `panel.png` too if present in both.
"""

import argparse
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
RMS_IMAGE_DIFF = os.path.join(REPO_ROOT, "_build", "stage", "app", "bin", "rmsImageDiff")

# Session-header properties that reflect UI/playback state rather than graph
# structure; drop whole GTO property lines whose name matches, so they can't
# cause spurious behavioral diffs.
_VOLATILE_PROP_RE = re.compile(
    r"^\s*(string sessionName|int currentFrame|int\[\] marks)\b"
)
# Absolute media paths vary by machine; canonicalize to a stable token.
_MOVIE_LINE_RE = re.compile(r'^(\s*string movie = ")([^"]+)("\s*)$')


def normalize_gto(text: str) -> str:
    """Return a canonical form of a text-GTO session for comparison."""
    home = os.path.expanduser("~")
    out_lines = []
    for line in text.splitlines():
        if _VOLATILE_PROP_RE.match(line):
            continue
        m = _MOVIE_LINE_RE.match(line)
        if m and (m.group(2).endswith(".mp4") or m.group(2).endswith(".mov")):
            line = '%s<MP4_FIXTURE>%s' % (m.group(1), m.group(3))
        else:
            line = line.replace(REPO_ROOT, "<REPO>").replace(home, "<HOME>")
        out_lines.append(line)
    return "\n".join(out_lines) + "\n"


def compare_gto(golden_path: str, actual_path: str) -> tuple[bool, str]:
    with open(golden_path, "r") as f:
        g = normalize_gto(f.read())
    with open(actual_path, "r") as f:
        a = normalize_gto(f.read())
    if g == a:
        return True, "behavioral: MATCH"
    # Produce a short unified diff for the report.
    import difflib
    diff = "\n".join(
        difflib.unified_diff(
            g.splitlines(), a.splitlines(),
            fromfile="golden", tofile="actual", lineterm="", n=2,
        )
    )
    return False, "behavioral: MISMATCH\n" + diff


def compare_png(golden_png: str, actual_png: str, dmax: float) -> tuple[bool, str]:
    if not os.path.isfile(RMS_IMAGE_DIFF):
        return False, f"pixel: rmsImageDiff not found at {RMS_IMAGE_DIFF}"
    proc = subprocess.run(
        [RMS_IMAGE_DIFF, "-cmp", "-dmax", str(dmax), "-m", golden_png, actual_png],
        capture_output=True, text=True,
    )
    ok = proc.returncode == 0
    return ok, f"pixel: {'MATCH' if ok else 'MISMATCH'} (dmax={dmax})\n{proc.stdout.strip()}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden-dir", required=True)
    ap.add_argument("--actual-dir", required=True)
    ap.add_argument("--dmax", type=float, default=0.0)
    args = ap.parse_args()

    results = []
    ok_all = True

    g_sess = os.path.join(args.golden_dir, "session.rv")
    a_sess = os.path.join(args.actual_dir, "session.rv")
    if os.path.isfile(g_sess) and os.path.isfile(a_sess):
        ok, msg = compare_gto(g_sess, a_sess)
        ok_all &= ok
        results.append(msg)
    else:
        ok_all = False
        results.append(f"behavioral: missing session.rv (golden={os.path.isfile(g_sess)}, actual={os.path.isfile(a_sess)})")

    # Compare every PNG artifact present in the golden dir (not just
    # panel.png -- popup-menu scenarios grab their own top-level window,
    # e.g. configmenu.png). A golden PNG with no matching actual PNG is a
    # hard FAIL, not a silently-skipped gate: a broken port that can't find
    # the widget (and so never writes the artifact) must not pass.
    golden_pngs = sorted(
        f for f in os.listdir(args.golden_dir) if f.endswith(".png")
    ) if os.path.isdir(args.golden_dir) else []
    for name in golden_pngs:
        g_png = os.path.join(args.golden_dir, name)
        a_png = os.path.join(args.actual_dir, name)
        if not os.path.isfile(a_png):
            ok_all = False
            results.append(f"pixel: missing actual {name} (golden exists)")
            continue
        ok, msg = compare_png(g_png, a_png, args.dmax)
        ok_all &= ok
        results.append(f"[{name}] {msg}")
    # (If the golden dir has no PNGs at all, the pixel gate simply isn't
    # exercised for this scenario.)

    print("\n".join(results))
    print("RESULT:", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
