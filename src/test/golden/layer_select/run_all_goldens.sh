#!/usr/bin/env bash
# Run all layer_select golden scenarios (Mu capture or Python port verify).
#
# Usage:
#   ./run_all_goldens.sh              # verify Python port (default)
#   IMPL=mu ./run_all_goldens.sh      # Mu determinism / re-baseline check
#   NO_XVFB=1 ./run_all_goldens.sh    # real display smoke (non-gated pixels)
#   ./run_all_goldens.sh ls_activate  # single scenario
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
NO_XVFB="${NO_XVFB:-0}"
COMPARE_BEHAVIORAL_ONLY="${COMPARE_BEHAVIORAL_ONLY:-0}"
# GATE: both | behavioral | pixel | default | runtime (see ../VERIFICATION.md)
GATE="${GATE:-both}"

# Harness: mode file stem != package directory name.
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
    ls_select_layer
    ls_select_default
    ls_widget_docked
    ls_widget_floating
    ls_widget_drag
    ls_floating_toggle
    ls_wheel_highlight
    ls_wheel_up
    ls_middle_click_layer
    ls_click_layer
    ls_hover_highlight
    ls_close_hover
    ls_close_click
    ls_stylus_select
    ls_popup_menu
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
    find "$SCENARIOS" -maxdepth 1 -name '*.py' ! -name '_ls_common.py' -printf '%f\n' \
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
pixel_fail=0
pixel_fail_list=""

if [ "$GATE" = "default" ]; then
    IMPL=default
fi

xvfb_note="xvfb+software-Mesa"
runner_extra=()
if [ "$NO_XVFB" = "1" ]; then
    xvfb_note="real-display (NO_XVFB=1)"
    runner_extra=(--no-xvfb)
fi
compare_note="behavioral+pixel dmax=$DMAX"
case "$GATE" in
    behavioral) compare_note="behavioral-only" ;;
    pixel)      compare_note="pixel-only dmax=$DMAX" ;;
    default)    compare_note="default-launch behavioral-only" ;;
    runtime)    compare_note="runtime-clean (no RV errors in rv.log)" ;;
esac
if [ "$COMPARE_BEHAVIORAL_ONLY" = "1" ]; then
    compare_note="behavioral-only"
fi

echo "layer_select goldens: impl=$IMPL gate=$GATE mode=$LS_MODE package=$LS_PACKAGE $xvfb_note compare=$compare_note timeout=${TIMEOUT}s (${#ids[@]} scenarios)"

for id in "${ids[@]}"; do
    if should_skip "$id"; then
        echo "SKIP $id (set LAYER_EXR_FIXTURE in fixtures/layers.env)"
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
    menu_bar_flag=""
    [ "$id" = "ls_activate_menu" ] && menu_bar_flag="--menu-bar"
    if ! python3 "$RUNNER" \
        --scenario "$scenario" \
        --out "$out" \
        --rv "$RV" \
        --impl "$IMPL" \
        --timeout "$TIMEOUT" \
        $menu_bar_flag \
        "${RUNNER_MODE[@]}" \
        "${runner_extra[@]}" >/dev/null 2>&1; then
        if [ "$GATE" = "runtime" ]; then
            echo "FAIL $id (runtime — see $out/rv.log and runtime_errors.txt)"
        else
            echo "FAIL $id (run_scenario)"
        fi
        fail=$((fail + 1))
        fail_list="$fail_list $id"
        continue
    fi
    if [ "$GATE" = "runtime" ]; then
        echo "PASS $id"
        pass=$((pass + 1))
        continue
    fi
    compare_out="$(python3 "$COMPARE" \
        --golden-dir "$golden_dir" \
        --actual-dir "$out" \
        --dmax "$DMAX" 2>&1)" || compare_rc=$?
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
                echo "$compare_out" | head -8
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
                echo "$compare_out" | head -8
                fail=$((fail + 1)); fail_list="$fail_list $id"
            fi
            ;;
        both)
            if [ "$compare_rc" -ne 0 ] && [ "$COMPARE_BEHAVIORAL_ONLY" = "1" ] && [ "$behavioral_ok" -eq 1 ]; then
                echo "PASS $id (behavioral OK; pixel differs — expected under NO_XVFB)"
                pass=$((pass + 1))
                pixel_fail=$((pixel_fail + 1))
                pixel_fail_list="$pixel_fail_list $id"
            elif [ "$compare_rc" -ne 0 ]; then
                echo "FAIL $id (compare)"
                echo "$compare_out" | head -8
                fail=$((fail + 1)); fail_list="$fail_list $id"
            else
                echo "PASS $id"
                pass=$((pass + 1))
            fi
            ;;
    esac
done

echo "---"
echo "PASS=$pass FAIL=$fail"
if [ "$pixel_fail" -gt 0 ]; then
    echo "PIXEL_DIFF_BEHAVIORAL_OK=$pixel_fail (non-blocking when COMPARE_BEHAVIORAL_ONLY=1):$pixel_fail_list"
fi
if [ "$fail" -gt 0 ]; then
    echo "Failed:$fail_list"
    exit 1
fi
