#!/usr/bin/env bash
# Write runtime_errors.txt for existing golden-mac/ baselines (Mu, one run each).
# Use when golden dirs predate runtime baseline capture.
#
# Usage: ./backfill_runtime_baselines_mac.sh [scenario_id ...]
#
set -euo pipefail

if [ -z "${CAFFEINATED:-}" ]; then
    export CAFFEINATED=1
    exec caffeinate -d -i "$0" "$@"
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$HERE"
REPO_ROOT="$(cd "$PKG/../../../.." && pwd)"
RUNNER="$REPO_ROOT/src/test/golden/harness/run_scenario.py"
RUNTIME_CHECK="$REPO_ROOT/src/test/golden/harness/runtime_log_check.py"
RV="${RV:-$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/RV}"
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden-mac"
TIMEOUT="${TIMEOUT:-600}"
LS_MODE="${LS_MODE:-layer_select_mode}"
LS_PACKAGE="${LS_PACKAGE:-layer_select}"
RUNNER_MODE=(--mode "$LS_MODE" --package "$LS_PACKAGE")

if [ -f "$PKG/fixtures/layers.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PKG/fixtures/layers.env"
    set +a
fi

ids=("$@")
if [ ${#ids[@]} -eq 0 ]; then
    while IFS= read -r id; do
        ids+=("$id")
    done < <(find "$GOLDEN" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
fi

if [ ${#ids[@]} -eq 0 ]; then
    echo "Nothing to backfill (no golden-mac/ baselines)."
    exit 0
fi

for id in "${ids[@]}"; do
    dest="$GOLDEN/$id"
    scenario="$SCENARIOS/${id}.py"
    if [ ! -f "$dest/session.rv" ] || [ ! -f "$scenario" ]; then
        echo "SKIP $id (missing golden or scenario)"
        continue
    fi
    out="/tmp/golden_runtime_backfill_${id}"
    rm -rf "$out"
    mkdir -p "$out"
    menu_bar_flag=""
    [ "$id" = "ls_activate_menu" ] && menu_bar_flag="--menu-bar"
    echo "==> $id"
    if ! python3 "$RUNNER" \
        --scenario "$scenario" --out "$out" --rv "$RV" \
        --impl mu --no-xvfb --timeout "$TIMEOUT" \
        --allow-runtime-errors \
        $menu_bar_flag \
        "${RUNNER_MODE[@]}" >/dev/null 2>&1; then
        echo "FAIL $id (run_scenario)"
        exit 1
    fi
    python3 "$RUNTIME_CHECK" --write-baseline "$out" "$dest/runtime_errors.txt"
    pkill -f "${RV} " 2>/dev/null || true
    sleep 0.3
done

echo "Backfill complete."
