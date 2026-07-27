#!/usr/bin/env bash
# GUI sanity gate: re-run every session_manager golden scenario against a REAL
# on-screen display (no Xvfb -- real GPU, compositor, and font stack).
#
# This is a gate, but NOT a scripted pixel pass/fail -- see
# ../VERIFICATION.md#gui-sanity-gate-real-display for the full rationale.
# Two independent checks run per scenario:
#
#   - Behavioral (node graph, via compare.py): exact, objective, HARD. A
#     mismatch here fails the run and this script's exit code, same as
#     run_all_goldens.sh.
#   - Pixel (panel.png etc., via compare.py --pixel-mode report): NO
#     threshold and NO verdict. Real GPU/font/compositor rendering is never
#     byte-identical to the pinned Xvfb+software-Mesa goldens, so there is no
#     dmax that is simultaneously loose enough to avoid noise and tight
#     enough to catch a real regression -- so this script does not pick one.
#     It prints RMS + max-diff location + both PNG paths per scenario instead
#     and leaves the judgment call to whoever (or whichever AI loop) reads the
#     output: does this look like acceptable rendering noise, or a real
#     regression that should count as a failure this iteration?
#
# Missing artifacts are still a hard fail in both cases (compare.py's own
# rule): whether a PNG got produced at all is objective, only its pixel
# content is left to review.
#
# A final phase (added 2026-07-24) then re-runs every scenario ONE more time
# with no --impl override at all -- an actual normal app launch, RV picking
# its own real default. This exists because a real bug (session_manager's
# panel unreachable via its real 'x' shortcut/menu on a normal launch) was
# found that this gate's own main loop above -- and every other gate in the
# repo -- missed, precisely because they all force an explicit --impl. That
# forcing is required for the Mu-vs-Python comparison the main loop does; the
# final phase exists specifically to still catch "the default path itself is
# broken," which the main loop structurally cannot see. Hard gate: missing
# artifacts and behavioral mismatch fail it, same rule as everywhere else.
#
# Usage:
#   ./run_gui_sanity_gate.sh              # all scenarios, real display
#   ./run_gui_sanity_gate.sh sm_nav       # single scenario
#   IMPL=mu ./run_gui_sanity_gate.sh      # Mu-side run (e.g. to eyeball what
#                                         # "normal" rendering noise looks like)
#
set -euo pipefail

# On macOS, re-exec under caffeinate -d -i so the display can't sleep
# mid-batch -- see capture_golden_mac.sh's header for why: display sleep
# mid-run changes the backing scale factor of later windows, which looks
# exactly like a pixel regression but isn't one. caffeinate is macOS-only,
# so this is a no-op (skipped) on Linux.
if [ "$(uname)" = "Darwin" ] && [ -z "${CAFFEINATED:-}" ]; then
    export CAFFEINATED=1
    exec caffeinate -d -i "$0" "$@"
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$HERE"
REPO_ROOT="$(cd "$PKG/../../../.." && pwd)"
RUNNER="$REPO_ROOT/src/test/golden/harness/run_scenario.py"
COMPARE="$REPO_ROOT/src/test/golden/harness/compare.py"
COMPARE_FLAGS=(--relax-render-path --relax-session-playback)
if [ -z "${RV:-}" ]; then
    if [ -f "$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/RV" ]; then
        RV="$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/RV"
    else
        RV="$REPO_ROOT/_build/stage/app/bin/rv"
    fi
fi
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden"
# On macOS the hard behavioral baseline lives in golden-mac/ (see COVERAGE.md);
# golden/ Linux Xvfb baselines are still used for the pixel report (cross-GPU).
BEHAVIORAL_GOLDEN="$GOLDEN"
PIXEL_GOLDEN="$GOLDEN"
if [ "$(uname)" = "Darwin" ]; then
    BEHAVIORAL_GOLDEN="$PKG/golden-mac"
fi
IMPL="${IMPL:-python}"
TIMEOUT="${TIMEOUT:-600}"

if [ -f "$PKG/fixtures/mp4.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PKG/fixtures/mp4.env"
    set +a
fi

SKIP_IDS=(
    sm_mp4_all
    sm_reopen_after_hide
    sm_toggle_diag
    sm_thumb_diag
    sm_thumb_diag2
    # KNOWN BUG, not "no baseline by design" like the above: addSources() +
    # waitForProgressiveLoading() hangs forever under a real display (no
    # Xvfb) -- confirmed 2026-07-24, root cause is native (RvSession::render()
    # never advances continueLoading() here; neither Qt event-pumping nor a
    # forced synchronous repaint on the real GL widget helped). Since this
    # script always runs --no-xvfb, it would hang on this scenario every time.
    # Un-skip once the native render/load path is fixed -- see
    # ../VERIFICATION.md#gui-sanity-gate-real-display. sm_media_add_sources
    # hits the exact same addSources()/waitForProgressiveLoading() path
    # (confirmed 2026-07-24) -- same root cause, not a second bug.
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

all_required_ids() {
    # -printf is GNU-only; BSD find (macOS default) doesn't have it and
    # silently errors, which previously made this yield zero IDs on Mac.
    # -exec basename {} \; works on both.
    find "$SCENARIOS" -maxdepth 1 -name '*.py' ! -name '_sm_common.py' -exec basename {} \; \
        | sed 's/\.py$//' | while read -r id; do
            should_skip "$id" && continue
            echo "$id"
        done | sort
}

ids=("$@")
if [ ${#ids[@]} -eq 0 ]; then
    # mapfile needs Bash 4+; macOS ships Bash 3.2 with no newer one on PATH
    # by default -- confirmed 2026-07-24 via the identical bug in
    # run_all_goldens_mac.sh's no-args path.
    ids=()
    while IFS= read -r id; do
        ids+=("$id")
    done < <(all_required_ids)
fi

pass=0
fail=0
fail_list=""
review_ids=""

echo "session_manager GUI sanity gate: impl=$IMPL mode=real-display (no Xvfb) (${#ids[@]} scenarios)"
if [ "$BEHAVIORAL_GOLDEN" != "$PIXEL_GOLDEN" ]; then
    echo "Behavioral baseline: $BEHAVIORAL_GOLDEN  Pixel report baseline: $PIXEL_GOLDEN"
fi
echo "Behavioral mismatches are hard FAILs. Pixel differences are reported, not gated --"
echo "review each [panel.png] INFO block below and judge rendering noise vs. real regression."
echo

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id"
        continue
    fi
    behavioral_golden_dir="$BEHAVIORAL_GOLDEN/$id"
    pixel_golden_dir="$PIXEL_GOLDEN/$id"
    scenario="$SCENARIOS/${id}.py"
    out="/tmp/gui_sanity_${id}"
    if [ ! -f "$behavioral_golden_dir/session.rv" ]; then
        echo "FAIL $id (no behavioral golden — run capture_golden_mac.sh or capture_golden.sh $id)"
        fail=$((fail + 1))
        fail_list="$fail_list $id"
        continue
    fi
    if [ ! -f "$scenario" ]; then
        echo "FAIL $id (missing scenario file)"
        fail=$((fail + 1))
        fail_list="$fail_list $id"
        continue
    fi
    rm -rf "$out"
    mkdir -p "$out"
    if ! python3 "$RUNNER" \
        --scenario "$scenario" \
        --out "$out" \
        --rv "$RV" \
        --impl "$IMPL" \
        --timeout "$TIMEOUT" \
        --no-xvfb >/dev/null 2>&1; then
        echo "FAIL $id (run_scenario)"
        fail=$((fail + 1))
        fail_list="$fail_list $id"
        continue
    fi
    compare_rc=0
    compare_out="$(python3 "$COMPARE" \
        --golden-dir "$pixel_golden_dir" \
        --behavioral-golden-dir "$behavioral_golden_dir" \
        --actual-dir "$out" \
        --pixel-mode report \
        "${COMPARE_FLAGS[@]}" 2>&1)" || compare_rc=$?
    if [ "$compare_rc" -ne 0 ]; then
        echo "FAIL $id (behavioral mismatch or missing artifact)"
        echo "$compare_out" | head -8
        fail=$((fail + 1))
        fail_list="$fail_list $id"
        continue
    fi
    if echo "$compare_out" | grep -q "pixel: INFO"; then
        review_ids="$review_ids $id"
        echo "PASS $id (behavioral OK — pixel report below needs review)"
        echo "$compare_out" | grep -A4 "pixel: INFO" | sed "s/^/    [$id] /"
    else
        echo "PASS $id"
    fi
    pass=$((pass + 1))
done

echo "---"
echo "PASS=$pass FAIL=$fail"
if [ -n "$review_ids" ]; then
    echo "NEEDS_AI_REVIEW:$review_ids"
    echo "^ behavioral gate passed for these; inspect the pixel INFO blocks above (or the"
    echo "  golden/actual PNGs directly) and judge whether each is acceptable real-display"
    echo "  rendering noise or a real regression. If real, treat it as a failure and iterate --"
    echo "  this script's exit code alone does not capture that judgment."
fi

# Final phase: launch exactly like a normal app -- no --impl, no RV_MODE_IMPL_*
# override at all, RV picks its own real, shipped default. Added 2026-07-24
# after a real bug (session_manager's panel unreachable via its real 'x'
# shortcut/menu on a normal launch) was found that every other gate in this
# repo missed, because every one of them -- this script's own main loop
# included -- always forces an explicit --impl. That's necessary for the
# Mu-vs-Python comparison the rest of this gate does, but it means none of
# them ever exercise RV's actual default mode-selection logic, which is
# exactly where that bug lived. This phase is a HARD gate on missing
# artifacts and behavioral mismatch (same compare.py rules as the main loop)
# -- it exists specifically to catch "the default path itself is broken,"
# not to re-litigate Mu vs Python.
echo
echo "--- Final phase: real display, no --impl override (launching like a normal app) ---"
default_pass=0
default_fail=0
default_fail_list=""
for id in "${ids[@]}"; do
    if should_skip "$id"; then
        continue
    fi
    behavioral_golden_dir="$BEHAVIORAL_GOLDEN/$id"
    pixel_golden_dir="$PIXEL_GOLDEN/$id"
    scenario="$SCENARIOS/${id}.py"
    out="/tmp/gui_sanity_default_${id}"
    if [ ! -f "$behavioral_golden_dir/session.rv" ] || [ ! -f "$scenario" ]; then
        continue  # already reported by the main loop above
    fi
    rm -rf "$out"
    mkdir -p "$out"
    if ! python3 "$RUNNER" \
        --scenario "$scenario" \
        --out "$out" \
        --rv "$RV" \
        --impl default \
        --timeout "$TIMEOUT" \
        --no-xvfb >/dev/null 2>&1; then
        echo "FAIL $id (default launch: run_scenario)"
        default_fail=$((default_fail + 1))
        default_fail_list="$default_fail_list $id"
        continue
    fi
    compare_rc=0
    compare_out="$(python3 "$COMPARE" \
        --golden-dir "$pixel_golden_dir" \
        --behavioral-golden-dir "$behavioral_golden_dir" \
        --actual-dir "$out" \
        --pixel-mode report \
        "${COMPARE_FLAGS[@]}" 2>&1)" || compare_rc=$?
    if [ "$compare_rc" -ne 0 ]; then
        echo "FAIL $id (default launch: behavioral mismatch or missing artifact -- e.g. a panel that never opened)"
        echo "$compare_out" | head -8
        default_fail=$((default_fail + 1))
        default_fail_list="$default_fail_list $id"
        continue
    fi
    default_pass=$((default_pass + 1))
done
echo "Default-launch phase: PASS=$default_pass FAIL=$default_fail"
if [ "$default_fail" -gt 0 ]; then
    echo "Default-launch failures (real bug in RV's own default startup path, not a"
    echo "harness/impl-selection artifact):$default_fail_list"
fi

if [ "$fail" -gt 0 ] || [ "$default_fail" -gt 0 ]; then
    echo "Failed:$fail_list$default_fail_list"
    exit 1
fi
