#!/usr/bin/env bash
# Capture Mu baselines for session_manager golden scenarios into golden/<id>/
# (Linux, Xvfb + software Mesa -- the pinned path golden/ baselines require).
#
# Determinism check (built in, not optional): a pixel gate at -dmax 0 is only
# trustworthy if capture is bit-reproducible on the machine running it -- see
# ../VERIFICATION.md's determinism requirements. This captures each scenario
# TWICE back-to-back and refuses to commit a baseline unless both captures
# are byte-identical (session.rv via diff, every PNG via `rmsImageDiff -m`
# reporting no max-diff line). A scenario that fails this check is skipped
# with an error, not committed with a caveat -- do not hand-copy a
# non-reproducing capture into golden/ to work around this. (Added
# 2026-07-24: previously this script captured once and committed
# unconditionally, so no existing golden/<id>/ baseline -- especially the
# real-thumbnail ones, sm_media_load/sm_mp4_load/sm_meridian_mp4_load, whose
# rvio-subprocess pipeline is exactly the kind of thing §H's own "open risk,
# not yet verified" note warns about -- had ever actually been confirmed
# reproducible on the machine that captured it.)
#
# Usage:
#   ./capture_golden.sh [scenario_id ...]   # default: all scenarios missing golden/
#   ./capture_golden.sh sm_media_load       # one scenario
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$HERE"
REPO_ROOT="$(cd "$PKG/../../../.." && pwd)"
RUNNER="$REPO_ROOT/src/test/golden/harness/run_scenario.py"
RMS_IMAGE_DIFF="${RMS_IMAGE_DIFF:-$REPO_ROOT/_build/stage/app/bin/rmsImageDiff}"
RV="${RV:-$REPO_ROOT/_build/stage/app/bin/rv}"
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden"
TIMEOUT="${TIMEOUT:-600}"

# Optional local media paths (see fixtures/mp4.env.example)
if [ -f "$PKG/fixtures/mp4.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PKG/fixtures/mp4.env"
    set +a
fi

# Integration-only / diagnostic: no committed golden baseline by design (these
# write only diag.txt, never session.rv -- capturing them hits the "did not
# produce session.rv" check below).
SKIP_IDS=(
    sm_mp4_all
    sm_reopen_after_hide
    sm_toggle_diag
    sm_thumb_diag
    sm_thumb_diag2
)

should_skip() {
    local id="$1"
    for s in "${SKIP_IDS[@]}"; do
        [ "$s" = "$id" ] && return 0
    done
    return 1
}

all_scenario_ids() {
    find "$SCENARIOS" -maxdepth 1 -name '*.py' ! -name '_sm_common.py' -printf '%f\n' \
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
    echo "Nothing to capture (all goldens present or only skipped IDs remain)."
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

echo "Capturing ${#ids[@]} scenario(s) with --impl mu (timeout=${TIMEOUT}s), 2x each for a determinism check"

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
    out1="/tmp/golden_capture_${id}_a"
    out2="/tmp/golden_capture_${id}_b"
    dest="$GOLDEN/$id"
    echo "==> $id (run 1/2)"
    rm -rf "$out1"
    mkdir -p "$out1"
    # Guarded (not a bare call): under set -e, a single timed-out/crashed
    # scenario would otherwise abort this whole batch instead of failing just
    # that one -- verified 2026-07-24 via the equivalent bug in
    # capture_golden_mac.sh (sm_meridian_mp4_load's run_scenario.py timeout
    # killed the entire script, silently, with no summary).
    if ! python3 "$RUNNER" \
        --scenario "$scenario" --out "$out1" --rv "$RV" \
        --impl mu --timeout "$TIMEOUT"; then
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
        --impl mu --timeout "$TIMEOUT"; then
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
    echo "Capture incomplete -- FAILED (not committed):$fail_list"
    echo "These did not reproduce identically across two runs, or timed out/crashed --"
    echo "investigate before re-running; do not retry in a loop hoping for a lucky match."
    exit 1
fi
echo "Capture complete."
