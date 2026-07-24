#!/usr/bin/env bash
# Capture Mac-native Mu baselines for session_manager golden scenarios into
# golden-mac/<id>/ -- a SEPARATE baseline set from golden/<id>/ (which is
# captured on Linux under Xvfb + software Mesa). The two are not
# interchangeable: real macOS rendering (Retina/HiDPI, Core Text, native GPU)
# does not match the Xvfb+software-Mesa pixel path even in raw dimensions
# (verified 2026-07-24: tree_readonly's Mac panel.png came out 638x1196 vs.
# the Linux golden's 319x598 -- exactly 2x, a HiDPI backing-scale-factor
# difference, before any content is even compared). Behavioral (session.rv)
# state, by contrast, was verified identical to the Linux golden -- the graph
# itself is platform-independent; only pixels need a native baseline.
#
# There is no Xvfb on macOS, so this always runs against the real display
# (--no-xvfb) -- that is expected and fine, not a fallback.
#
# Determinism check (built in, not optional): a pixel gate at -dmax 0 is only
# trustworthy if capture is bit-reproducible on the machine running it -- see
# ../VERIFICATION.md's determinism requirements. This script captures each
# scenario TWICE back-to-back and refuses to commit a baseline unless both
# captures are byte-identical (session.rv via diff, every PNG via
# `rmsImageDiff -m` reporting no max-diff line). A scenario that fails this
# check is skipped with an error, not committed with a caveat -- do not
# hand-copy a non-reproducing capture into golden-mac/ to work around this.
#
# Usage:
#   ./capture_golden_mac.sh [scenario_id ...]   # default: all scenarios missing golden-mac/
#   ./capture_golden_mac.sh sm_nav              # one scenario
#
set -euo pipefail

# Re-exec under caffeinate -d -i so the display can't sleep mid-batch. Fixed
# 2026-07-24: a long unattended full-batch capture ran past this machine's
# displaysleep timeout (180s); RV windows launched after the display slept
# and woke came back at a different backing scale factor (319x598) than the
# ones launched before (638x1196) -- not a real behavioral difference, pure
# environment drift, and it silently corrupted that entire capture batch.
# QT_ENABLE_HIGHDPI_SCALING/QT_SCALE_FACTOR alone did NOT fix this (tested):
# the panel grab reads the screen's actual backing scale directly, so the
# only real fix is preventing the sleep event itself.
if [ -z "${CAFFEINATED:-}" ]; then
    export CAFFEINATED=1
    exec caffeinate -d -i "$0" "$@"
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$HERE"
REPO_ROOT="$(cd "$PKG/../../../.." && pwd)"
RUNNER="$REPO_ROOT/src/test/golden/harness/run_scenario.py"
RMS_IMAGE_DIFF="${RMS_IMAGE_DIFF:-$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/rmsImageDiff}"
RV="${RV:-$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/RV}"
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden-mac"
TIMEOUT="${TIMEOUT:-600}"

if [ -f "$PKG/fixtures/mp4.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PKG/fixtures/mp4.env"
    set +a
fi

# Integration-only / diagnostic: no committed golden baseline by design.
SKIP_IDS=(
    sm_mp4_all
    sm_reopen_after_hide
    sm_toggle_diag
    sm_thumb_diag
    sm_thumb_diag2
    # KNOWN BUG, not "no baseline by design" like the above: addSources() +
    # waitForProgressiveLoading() hangs forever under a real display --
    # confirmed 2026-07-24 (native RvSession::render() never advances the
    # load here; not fixable from the Python/test side, see the note in
    # ../VERIFICATION.md#mac-native-gate). Without this, capturing it burns a
    # full 600s timeout every attempt. Un-skip once the native bug is fixed.
    # sm_media_add_sources hits the exact same code path -- same root cause,
    # confirmed 2026-07-24, not a second bug.
    sm_meridian_mp4_load
    sm_media_add_sources
)

should_skip() {
    local id="$1"
    for s in "${SKIP_IDS[@]}"; do
        [ "$s" = "$id" ] && return 0
    done
    return 1
}

all_scenario_ids() {
    # -printf is GNU-only; BSD find (macOS default) doesn't have it and
    # silently errors, which previously made this yield zero IDs on Mac
    # (confirmed 2026-07-24: a no-args run reported "nothing to capture" and
    # captured nothing). -exec basename {} \; works on both.
    find "$SCENARIOS" -maxdepth 1 -name '*.py' ! -name '_sm_common.py' -exec basename {} \; \
        | sed 's/\.py$//' | sort
}

ids=("$@")
if [ ${#ids[@]} -eq 0 ]; then
    while IFS= read -r id; do
        should_skip "$id" && continue
        [ -f "$GOLDEN/$id/session.rv" ] && continue
        ids+=("$id")
    done < <(all_scenario_ids)
fi

if [ ${#ids[@]} -eq 0 ]; then
    echo "Nothing to capture (all golden-mac baselines present or only skipped IDs remain)."
    exit 0
fi

# Returns 0 (identical) or 1 (differs); prints nothing on identical, a short
# reason otherwise. rmsImageDiff's -cmp exit code cannot be trusted (see
# ../VERIFICATION.md's pixel-gate bugfix note) so this uses -m: the "max diff
# at (...)" line is only ever printed when a nonzero difference was found.
pngs_identical() {
    local a="$1" b="$2"
    local out
    out="$("$RMS_IMAGE_DIFF" -m "$a" "$b" 2>&1)" || {
        echo "rmsImageDiff failed: $out"
        return 1
    }
    if echo "$out" | grep -q "max diff at"; then
        echo "$out" | grep "max diff at"
        return 1
    fi
    return 0
}

echo "Capturing ${#ids[@]} scenario(s) with --impl mu --no-xvfb (timeout=${TIMEOUT}s), 2x each for a determinism check"

fail=0
fail_list=""

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id (integration/diagnostic)"
        continue
    fi
    scenario="$SCENARIOS/${id}.py"
    if [ ! -f "$scenario" ]; then
        echo "ERROR: missing scenario $scenario" >&2
        exit 2
    fi
    out1="/tmp/golden_mac_capture_${id}_a"
    out2="/tmp/golden_mac_capture_${id}_b"
    dest="$GOLDEN/$id"
    echo "==> $id (run 1/2)"
    rm -rf "$out1"
    mkdir -p "$out1"
    if ! python3 "$RUNNER" \
        --scenario "$scenario" --out "$out1" --rv "$RV" \
        --impl mu --no-xvfb --timeout "$TIMEOUT"; then
        echo "FAIL $id (run_scenario exited non-zero on run 1 -- timeout or crash)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    if [ ! -f "$out1/session.rv" ]; then
        echo "FAIL $id (run 1 did not produce session.rv)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    echo "==> $id (run 2/2, determinism check)"
    rm -rf "$out2"
    mkdir -p "$out2"
    if ! python3 "$RUNNER" \
        --scenario "$scenario" --out "$out2" --rv "$RV" \
        --impl mu --no-xvfb --timeout "$TIMEOUT"; then
        echo "FAIL $id (run_scenario exited non-zero on run 2 -- timeout or crash)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    if [ ! -f "$out2/session.rv" ]; then
        echo "FAIL $id (run 2 did not produce session.rv)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi

    det_ok=1
    if ! diff -q "$out1/session.rv" "$out2/session.rv" >/dev/null 2>&1; then
        echo "FAIL $id: session.rv differs between two back-to-back runs -- not deterministic, not committing"
        det_ok=0
    fi
    for png in "$out1"/*.png; do
        [ -f "$png" ] || continue
        name="$(basename "$png")"
        if [ ! -f "$out2/$name" ]; then
            echo "FAIL $id: $name missing from run 2 -- not deterministic, not committing"
            det_ok=0
            continue
        fi
        if ! pngs_identical "$png" "$out2/$name"; then
            echo "FAIL $id: $name differs between two back-to-back runs -- not deterministic, not committing"
            det_ok=0
        fi
    done
    if [ "$det_ok" -ne 1 ]; then
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi

    rm -rf "$dest"
    mkdir -p "$dest"
    cp "$out1/session.rv" "$dest/"
    for png in "$out1"/*.png; do
        [ -f "$png" ] || continue
        cp "$png" "$dest/"
    done
    echo "    -> $dest ($(ls "$dest" | tr '\n' ' ')) [determinism check passed]"
done

echo "---"
if [ "$fail" -gt 0 ]; then
    echo "FAILED (not committed):$fail_list"
    echo "These did not reproduce identically across two runs on this machine -- investigate"
    echo "before re-running (see ../VERIFICATION.md's determinism requirements); do not retry"
    echo "in a loop hoping for a lucky match."
    exit 1
fi
echo "Capture complete."
