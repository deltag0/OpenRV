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
# Usage:
#   ./run_gui_sanity_gate.sh              # all scenarios, real display
#   ./run_gui_sanity_gate.sh sm_nav       # single scenario
#   IMPL=mu ./run_gui_sanity_gate.sh      # Mu-side run (e.g. to eyeball what
#                                         # "normal" rendering noise looks like)
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$HERE"
REPO_ROOT="$(cd "$PKG/../../../.." && pwd)"
RUNNER="$REPO_ROOT/src/test/golden/harness/run_scenario.py"
COMPARE="$REPO_ROOT/src/test/golden/harness/compare.py"
RV="${RV:-$REPO_ROOT/_build/stage/app/bin/rv}"
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden"
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
    mapfile -t ids < <(all_required_ids)
fi

pass=0
fail=0
fail_list=""
review_ids=""

echo "session_manager GUI sanity gate: impl=$IMPL mode=real-display (no Xvfb) (${#ids[@]} scenarios)"
echo "Behavioral mismatches are hard FAILs. Pixel differences are reported, not gated --"
echo "review each [panel.png] INFO block below and judge rendering noise vs. real regression."
echo

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id"
        continue
    fi
    golden_dir="$GOLDEN/$id"
    scenario="$SCENARIOS/${id}.py"
    out="/tmp/gui_sanity_${id}"
    if [ ! -f "$golden_dir/session.rv" ]; then
        echo "FAIL $id (no golden baseline — run capture_golden.sh $id)"
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
        --golden-dir "$golden_dir" \
        --actual-dir "$out" \
        --pixel-mode report 2>&1)" || compare_rc=$?
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
if [ "$fail" -gt 0 ]; then
    echo "Failed:$fail_list"
    exit 1
fi
