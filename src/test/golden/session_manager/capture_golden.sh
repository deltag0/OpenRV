#!/usr/bin/env bash
# Capture Mu baselines for session_manager golden scenarios.
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
RV="${RV:-$REPO_ROOT/_build/stage/app/bin/rv}"
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden"
TIMEOUT="${TIMEOUT:-600}"

# Integration-only: no committed golden baseline (env-specific, multi-hour).
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

echo "Capturing ${#ids[@]} scenario(s) with --impl mu (timeout=${TIMEOUT}s)"

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id (integration/diagnostic)"
        continue
    fi
    scenario="$SCENARIOS/${id}.py"
    out="/tmp/golden_capture_${id}"
    dest="$GOLDEN/$id"
    if [ ! -f "$scenario" ]; then
        echo "ERROR: missing scenario $scenario" >&2
        exit 2
    fi
    echo "==> $id"
    rm -rf "$out"
    mkdir -p "$out"
    python3 "$RUNNER" \
        --scenario "$scenario" \
        --out "$out" \
        --rv "$RV" \
        --impl mu \
        --timeout "$TIMEOUT"
    if [ ! -f "$out/session.rv" ]; then
        echo "ERROR: $id did not produce session.rv" >&2
        exit 1
    fi
    rm -rf "$dest"
    mkdir -p "$dest"
    cp "$out/session.rv" "$dest/"
    for png in "$out"/*.png; do
        [ -f "$png" ] || continue
        cp "$png" "$dest/"
    done
    echo "    -> $dest ($(ls "$dest" | tr '\n' ' '))"
done

echo "Capture complete."
