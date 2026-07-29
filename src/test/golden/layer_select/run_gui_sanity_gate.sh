#!/usr/bin/env bash
# GUI sanity gate for layer_select — real display, behavioral hard, pixel report-only.
#
# Runs ONLY after migration loop gates 1+2 pass (see ../VERIFICATION.md).
# On macOS compares behavioral against golden-mac/ (self-consistent native baselines).
#
# Usage:
#   ./run_gui_sanity_gate.sh
#   IMPL=python ./run_gui_sanity_gate.sh ls_widget_docked
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
COMPARE="$REPO_ROOT/src/test/golden/harness/compare.py"
RV="${RV:-$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/RV}"
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden-mac"
IMPL="${IMPL:-python}"
TIMEOUT="${TIMEOUT:-600}"

LS_MODE="${LS_MODE:-layer_select_mode}"
LS_PACKAGE="${LS_PACKAGE:-layer_select}"
RUNNER_MODE=(--mode "$LS_MODE" --package "$LS_PACKAGE")

LS_FIXTURES="$PKG/fixtures"
DEFAULT_LAYER_EXR="$LS_FIXTURES/test_layers.exr"

if [ -f "$PKG/fixtures/layers.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PKG/fixtures/layers.env"
    set +a
fi

EXR_REQUIRED_IDS=(
    ls_select_layer ls_select_default ls_widget_docked ls_widget_floating
    ls_widget_drag ls_floating_toggle ls_wheel_highlight ls_wheel_up
    ls_middle_click_layer ls_click_layer ls_hover_highlight ls_close_hover
    ls_close_click ls_stylus_select ls_popup_menu
)

needs_exr() {
    local id="$1"
    for s in "${EXR_REQUIRED_IDS[@]}"; do
        [ "$s" = "$id" ] && return 0
    done
    return 1
}

should_skip() {
    local id="$1"
    if needs_exr "$id"; then
        if [ -n "${LAYER_EXR_FIXTURE:-}" ] && [ -f "${LAYER_EXR_FIXTURE}" ]; then
            return 1
        fi
        if [ -f "$DEFAULT_LAYER_EXR" ]; then
            return 1
        fi
        return 0
    fi
    return 1
}

all_required_ids() {
    find "$SCENARIOS" -maxdepth 1 -name '*.py' ! -name '_ls_common.py' -exec basename {} \; \
        | sed 's/\.py$//' | while read -r id; do
            should_skip "$id" && continue
            echo "$id"
        done | sort
}

ids=("$@")
if [ ${#ids[@]} -eq 0 ]; then
    ids=()
    while IFS= read -r id; do
        ids+=("$id")
    done < <(all_required_ids)
fi

pass=0
fail=0
fail_list=""
review_ids=""

echo "layer_select GUI sanity: impl=$IMPL real-display (${#ids[@]} scenarios)"
echo "Behavioral: HARD vs $GOLDEN. Pixel: report-only — AI/human must review NEEDS_AI_REVIEW."
echo

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id"
        continue
    fi
    golden_dir="$GOLDEN/$id"
    scenario="$SCENARIOS/${id}.py"
    out="/tmp/ls_gui_sanity_${id}"
    if [ ! -f "$golden_dir/session.rv" ]; then
        echo "FAIL $id (no golden-mac baseline)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    rm -rf "$out"
    mkdir -p "$out"
    menu_bar_flag=""
    [ "$id" = "ls_activate_menu" ] && menu_bar_flag="--menu-bar"
    if ! python3 "$RUNNER" \
        --scenario "$scenario" --out "$out" --rv "$RV" \
        --impl "$IMPL" --no-xvfb --timeout "$TIMEOUT" \
        $menu_bar_flag \
        "${RUNNER_MODE[@]}" >/dev/null 2>&1; then
        echo "FAIL $id (run_scenario)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    compare_rc=0
    compare_out="$(python3 "$COMPARE" \
        --golden-dir "$golden_dir" \
        --behavioral-golden-dir "$golden_dir" \
        --actual-dir "$out" \
        --pixel-mode report 2>&1)" || compare_rc=$?
    if [ "$compare_rc" -ne 0 ]; then
        echo "FAIL $id (behavioral mismatch or missing artifact)"
        echo "$compare_out" | head -8
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    if echo "$compare_out" | grep -q "pixel: INFO"; then
        review_ids="$review_ids $id"
        echo "PASS $id (behavioral OK — pixel report needs review)"
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
    echo "^ Inspect pixel INFO blocks or PNG paths; real regression = iteration failure."
fi

if [ "$fail" -gt 0 ]; then
    echo "Failed:$fail_list"
    exit 1
fi
