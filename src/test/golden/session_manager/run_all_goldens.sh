#!/usr/bin/env bash
# Run all session_manager golden scenarios (Mu capture or Python port verify).
#
# Usage:
#   ./run_all_goldens.sh              # verify Python port (default)
#   IMPL=mu ./run_all_goldens.sh      # Mu determinism / re-baseline check
#   ./run_all_goldens.sh sm_nav        # single scenario
#
# Exit 0 only if every scenario passes run_scenario + compare.py at -dmax 0.
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
DMAX="${DMAX:-0}"

# Optional local media paths (see fixtures/mp4.env.example)
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
)

should_skip() {
    local id="$1"
    for s in "${SKIP_IDS[@]}"; do
        [ "$s" = "$id" ] && return 0
    done
    return 1
}

all_required_ids() {
    find "$SCENARIOS" -maxdepth 1 -name '*.py' ! -name '_sm_common.py' -printf '%f\n' \
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

echo "session_manager goldens: impl=$IMPL timeout=${TIMEOUT}s dmax=$DMAX (${#ids[@]} scenarios)"

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id"
        continue
    fi
    golden_dir="$GOLDEN/$id"
    scenario="$SCENARIOS/${id}.py"
    out="/tmp/golden_${id}"
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
        --timeout "$TIMEOUT" >/dev/null 2>&1; then
        echo "FAIL $id (run_scenario)"
        fail=$((fail + 1))
        fail_list="$fail_list $id"
        continue
    fi
    if ! python3 "$COMPARE" \
        --golden-dir "$golden_dir" \
        --actual-dir "$out" \
        --dmax "$DMAX" >/dev/null 2>&1; then
        echo "FAIL $id (compare)"
        python3 "$COMPARE" --golden-dir "$golden_dir" --actual-dir "$out" --dmax "$DMAX" 2>&1 | head -8
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
