#!/usr/bin/env bash
# Run layer_select goldens against golden-mac/ (macOS native display).
#
# Usage:
#   ./run_all_goldens_mac.sh              # verify Python port (default)
#   IMPL=mu ./run_all_goldens_mac.sh      # Mu determinism check
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
DMAX="${DMAX:-0}"
# GATE: both (default) | behavioral | pixel | default | runtime
#   behavioral — gate 1 only (session.rv)
#   pixel      — gate 2 only (PNG artifacts)
#   both       — gates 1+2 (full compare)
#   default    — gate 3: run scenarios with --impl default, behavioral only
#   runtime    — gate 0: no NEW runtime errors vs Mu golden runtime_errors.txt
GATE="${GATE:-both}"

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

if [ "$GATE" = "default" ]; then
    IMPL=default
fi

gate_note="behavioral+pixel dmax=$DMAX"
case "$GATE" in
    behavioral) gate_note="behavioral-only" ;;
    pixel)      gate_note="pixel-only dmax=$DMAX" ;;
    default)    gate_note="default-launch behavioral-only" ;;
    runtime)    gate_note="runtime delta vs Mu golden (runtime_errors.txt)" ;;
esac

echo "layer_select goldens (Mac): impl=$IMPL gate=$GATE ($gate_note) timeout=${TIMEOUT}s (${#ids[@]} scenarios)"

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id"
        continue
    fi
    golden_dir="$GOLDEN/$id"
    scenario="$SCENARIOS/${id}.py"
    out="/tmp/golden_${id}"
    if [ ! -f "$golden_dir/session.rv" ]; then
        echo "FAIL $id (no golden-mac baseline — run capture_golden_mac.sh $id)"
        fail=$((fail + 1)); fail_list="$fail_list $id"
        continue
    fi
    rm -rf "$out"
    mkdir -p "$out"
    menu_bar_flag=""
    [ "$id" = "ls_activate_menu" ] && menu_bar_flag="--menu-bar"
    runtime_golden_flag=(--runtime-golden-dir "$golden_dir")
    if ! python3 "$RUNNER" \
        --scenario "$scenario" --out "$out" --rv "$RV" \
        --impl "$IMPL" --no-xvfb --timeout "$TIMEOUT" \
        $menu_bar_flag \
        "${RUNNER_MODE[@]}" \
        "${runtime_golden_flag[@]}" >/dev/null 2>&1; then
        if [ "$GATE" = "runtime" ]; then
            echo "FAIL $id (runtime — new errors vs golden; see $out/runtime_errors.txt)"
        else
            echo "FAIL $id (run_scenario)"
        fi
        fail=$((fail + 1)); fail_list="$fail_list $id"
        pkill -f "${RV} " 2>/dev/null || true
        sleep 0.3
        continue
    fi
    if [ "$GATE" = "runtime" ]; then
        echo "PASS $id"
        pass=$((pass + 1))
        pkill -f "${RV} " 2>/dev/null || true
        sleep 0.3
        continue
    fi
    compare_rc=0
    compare_out="$(python3 "$COMPARE" \
        --golden-dir "$golden_dir" --actual-dir "$out" --dmax "$DMAX" 2>&1)" || compare_rc=$?
    compare_rc=${compare_rc:-0}
    behavioral_ok=0
    pixel_ok=0
    if echo "$compare_out" | grep -q "^behavioral: MATCH"; then
        behavioral_ok=1
    fi
    if echo "$compare_out" | grep -q "pixel: MATCH"; then
        pixel_ok=1
    fi
    has_png_golden=0
    if compgen -G "$golden_dir/*.png" >/dev/null 2>&1; then
        has_png_golden=1
    fi
    case "$GATE" in
        behavioral|default)
            if [ "$behavioral_ok" -eq 1 ]; then
                echo "PASS $id"
                pass=$((pass + 1))
            else
                echo "FAIL $id (behavioral)"
                echo "$compare_out" | head -10
                fail=$((fail + 1)); fail_list="$fail_list $id"
            fi
            ;;
        pixel)
            if [ "$has_png_golden" -eq 0 ]; then
                echo "PASS $id (no PNG baseline)"
                pass=$((pass + 1))
            elif [ "$pixel_ok" -eq 1 ]; then
                echo "PASS $id"
                pass=$((pass + 1))
            else
                echo "FAIL $id (pixel)"
                echo "$compare_out" | head -10
                fail=$((fail + 1)); fail_list="$fail_list $id"
            fi
            ;;
        both)
            if [ "$compare_rc" -eq 0 ]; then
                echo "PASS $id"
                pass=$((pass + 1))
            else
                echo "FAIL $id (compare)"
                echo "$compare_out" | head -10
                fail=$((fail + 1)); fail_list="$fail_list $id"
            fi
            ;;
    esac
    # Avoid zombie RV processes causing later scenario timeouts.
    pkill -f "${RV} " 2>/dev/null || true
    sleep 0.3
done

echo "--- PASS=$pass FAIL=$fail"
if [ "$fail" -gt 0 ]; then
    echo "Failed:$fail_list"
    exit 1
fi
