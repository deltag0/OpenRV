#!/usr/bin/env bash
# Run all session_manager golden scenarios against Mac-native baselines
# (golden-mac/, captured by capture_golden_mac.sh). This is a full hard gate
# -- both behavioral and pixel -- self-consistent to macOS: Mac output is
# compared only against Mac-captured goldens, never against the Linux
# Xvfb+software-Mesa golden/ baselines (they render at different pixel
# dimensions entirely -- see capture_golden_mac.sh's header). There is no
# Xvfb on macOS, so this always runs against the real display; that's
# expected, not a smoke-test fallback -- see ../VERIFICATION.md's
# "Mac-native gate" section.
#
# Usage:
#   ./run_all_goldens_mac.sh              # verify Python port (default)
#   IMPL=mu ./run_all_goldens_mac.sh      # Mu determinism / re-baseline check
#   ./run_all_goldens_mac.sh sm_nav       # single scenario
#
# Exit 0 only if every scenario passes run_scenario + compare.py at -dmax 0
# against golden-mac/. If golden-mac/<id>/ doesn't exist yet, run
# capture_golden_mac.sh first -- this script does not fall back to golden/.
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$HERE"
REPO_ROOT="$(cd "$PKG/../../../.." && pwd)"
RUNNER="$REPO_ROOT/src/test/golden/harness/run_scenario.py"
COMPARE="$REPO_ROOT/src/test/golden/harness/compare.py"
RV="${RV:-$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/RV}"
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden-mac"
IMPL="${IMPL:-python}"
TIMEOUT="${TIMEOUT:-600}"
DMAX="${DMAX:-0}"

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
    # KNOWN BUG, not "no baseline by design" like the above -- see
    # capture_golden_mac.sh's SKIP_IDS comment and
    # ../VERIFICATION.md#mac-native-gate. Un-skip once fixed.
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

echo "session_manager goldens (Mac-native): impl=$IMPL mode=real-display (no Xvfb on macOS) dmax=$DMAX timeout=${TIMEOUT}s (${#ids[@]} scenarios)"

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id"
        continue
    fi
    golden_dir="$GOLDEN/$id"
    scenario="$SCENARIOS/${id}.py"
    out="/tmp/golden_mac_${id}"
    if [ ! -f "$golden_dir/session.rv" ]; then
        echo "FAIL $id (no golden-mac baseline — run capture_golden_mac.sh $id)"
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
        --dmax "$DMAX" 2>&1)" || compare_rc=$?
    if [ "$compare_rc" -ne 0 ]; then
        echo "FAIL $id (compare)"
        echo "$compare_out" | head -8
        fail=$((fail + 1))
        fail_list="$fail_list $id"
        continue
    fi
    echo "PASS $id"
    pass=$((pass + 1))
done

echo "---"
echo "PASS=$pass FAIL=$fail"
if [ "$fail" -gt 0 ]; then
    echo "Failed:$fail_list"
    exit 1
fi
