#!/usr/bin/env bash
# Capture Mac-native Mu baselines for layer_select into golden-mac/<id>/.
#
# Usage:
#   ./capture_golden_mac.sh [scenario_id ...]
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
RMS_IMAGE_DIFF="${RMS_IMAGE_DIFF:-$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/rmsImageDiff}"
RV="${RV:-$REPO_ROOT/_build/stage/app/RV.app/Contents/MacOS/RV}"
SCENARIOS="$PKG/scenarios"
GOLDEN="$PKG/golden-mac"
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

all_scenario_ids() {
    find "$SCENARIOS" -maxdepth 1 -name '*.py' ! -name '_ls_common.py' -exec basename {} \; \
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
    echo "Nothing to capture (all golden-mac baselines present or skipped)."
    exit 0
fi

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

echo "Capturing ${#ids[@]} layer_select scenario(s) --impl mu --no-xvfb, 2x determinism"

fail=0
fail_list=""

for id in "${ids[@]}"; do
    menu_bar_flag=""
    [ "$id" = "ls_activate_menu" ] && menu_bar_flag="--menu-bar"
    if should_skip "$id"; then
        echo "SKIP $id (no EXR fixture)"
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
        --impl mu --no-xvfb --timeout "$TIMEOUT" \
        --allow-runtime-errors \
        "${RUNNER_MODE[@]}" $menu_bar_flag; then
        echo "FAIL $id (run 1)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    if [ ! -f "$out1/session.rv" ]; then
        echo "FAIL $id (no session.rv run 1)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    echo "==> $id (run 2/2)"
    rm -rf "$out2"
    mkdir -p "$out2"
    if ! python3 "$RUNNER" \
        --scenario "$scenario" --out "$out2" --rv "$RV" \
        --impl mu --no-xvfb --timeout "$TIMEOUT" \
        --allow-runtime-errors \
        "${RUNNER_MODE[@]}" $menu_bar_flag; then
        echo "FAIL $id (run 2)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    if [ ! -f "$out2/session.rv" ]; then
        echo "FAIL $id (no session.rv run 2)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi

    det_ok=1
    if ! diff -q "$out1/session.rv" "$out2/session.rv" >/dev/null 2>&1; then
        echo "FAIL $id: session.rv not deterministic"
        det_ok=0
    fi
    tmp1="$(mktemp)" tmp2="$(mktemp)"
    python3 "$RUNTIME_CHECK" --write-baseline "$out1" "$tmp1" >/dev/null
    python3 "$RUNTIME_CHECK" --write-baseline "$out2" "$tmp2" >/dev/null
    if ! diff -q "$tmp1" "$tmp2" >/dev/null 2>&1; then
        echo "FAIL $id: runtime_errors.txt not deterministic"
        det_ok=0
    fi
    rm -f "$tmp1" "$tmp2"
    for png in "$out1"/*.png; do
        [ -f "$png" ] || continue
        name="$(basename "$png")"
        if [ ! -f "$out2/$name" ]; then
            echo "FAIL $id: $name missing run 2"
            det_ok=0
            continue
        fi
        if ! pngs_identical "$png" "$out2/$name"; then
            echo "FAIL $id: $name not deterministic"
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
    python3 "$RUNTIME_CHECK" --write-baseline "$out1" "$dest/runtime_errors.txt"
    for png in "$out1"/*.png; do
        [ -f "$png" ] || continue
        cp "$png" "$dest/"
    done
    echo "    -> $dest ($(ls "$dest" | tr '\n' ' '))"
done

echo "---"
if [ "$fail" -gt 0 ]; then
    echo "FAILED:$fail_list"
    exit 1
fi
echo "Capture complete."
