#!/usr/bin/env bash
# Full migration loop — layer_select (macOS, golden-mac/).
#
# Runs all 5 mandatory gates in order; sanity + review agent run ONLY when gates 0+1+2 pass.
# The AI agent re-runs this entire script after each fix until exit 0 (max 15 runs).
# On infrastructure blockers (mode activation, harness, rvpkg, render bridge), keep
# debugging and fixing in-session until unblocked — see VERIFICATION.md § "When you hit
# a blocker — keep going until unblocked".
#
# Usage:
#   ./run_migration_loop_mac.sh
#   SKIP_SANITY=1 ./run_migration_loop_mac.sh
#   SKIP_REVIEW=1 ./run_migration_loop_mac.sh
#   SKIP_PIXEL_GATE=1 ./run_migration_loop_mac.sh   # accept Gate 2 failure, run Gates 3+4
#
# AI instructions: .agents/skills/mu-python-migration/SKILL.md §5
# Verification contract: src/test/golden/VERIFICATION.md
#
set -euo pipefail

if [ -z "${CAFFEINATED:-}" ]; then
    export CAFFEINATED=1
    exec caffeinate -d -i "$0" "$@"
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../../.." && pwd)"
GOLDEN_PKG_DIR="$HERE"
# shellcheck disable=SC1091
source "$REPO_ROOT/src/test/golden/harness/migration_loop_agent_reminder.sh"
SKIP_SANITY="${SKIP_SANITY:-0}"
SKIP_REVIEW="${SKIP_REVIEW:-0}"

echo "=============================================="
echo "layer_select migration loop (Mac)"
echo "See: $REPO_ROOT/src/test/golden/VERIFICATION.md"
echo "=============================================="

echo
echo ">>> GATE 0 (MANDATORY): Runtime clean — no RV errors during Python scenarios"
echo "    (see src/test/golden/harness/runtime_log_check.py; rv.log per scenario under /tmp/golden_*)"
if ! GATE=runtime IMPL=python "$HERE/run_all_goldens_mac.sh"; then
    echo "GATE 0 FAILED — new runtime errors vs Mu golden (see runtime_errors.txt under /tmp/golden_*)"
    exit 1
fi

echo
echo ">>> GATE 1 (MANDATORY): Behavioral — Python vs golden-mac/session.rv"
if ! GATE=behavioral IMPL=python "$HERE/run_all_goldens_mac.sh"; then
    echo "GATE 1 FAILED — fix Python port, then re-run ./run_migration_loop_mac.sh"
    exit 1
fi

echo ">>> GATE 2 (MANDATORY): Pixel — Python vs golden-mac/*.png at dmax=0"
if ! GATE=pixel IMPL=python "$HERE/run_all_goldens_mac.sh"; then
    if [ "${SKIP_PIXEL_GATE:-0}" = "1" ]; then
        echo "GATE 2 FAILED — SKIP_PIXEL_GATE=1, continuing to Gates 3+4 (accepted pixel mismatch)"
    else
        echo "GATE 2 FAILED — fix render/layout, then re-run ./run_migration_loop_mac.sh"
        echo "See: $HERE/BLOCKER.md (current open blocker)"
        echo "Or: SKIP_PIXEL_GATE=1 ./run_migration_loop_mac.sh to accept and run Gates 3+4"
        exit 1
    fi
else
    echo "GATE 2 PASSED"
fi

if [ "${SKIP_PIXEL_GATE:-0}" = "1" ]; then
    echo
    echo ">>> Gates 0+1 passed; Gate 2 skipped or failed (SKIP_PIXEL_GATE=1) — running Gates 3+4"
else
    echo
    echo ">>> Gates 0+1+2 PASSED — running conditional steps (sanity + review)"
fi

if [ "${SKIP_PIXEL_GATE:-0}" != "1" ]; then
    if [ "$SKIP_SANITY" = "1" ]; then
        echo "SKIP sanity (SKIP_SANITY=1)"
    else
        echo
        echo ">>> SANITY (conditional): GUI real-display gate"
        if ! "$HERE/run_gui_sanity_gate.sh"; then
            echo "SANITY FAILED (behavioral) — fix, then re-run ./run_migration_loop_mac.sh"
            exit 1
        fi
        echo "SANITY: If NEEDS_AI_REVIEW lines appeared above, judge pixel reports (VERIFICATION.md)."
    fi

    if [ "$SKIP_REVIEW" = "1" ]; then
        echo "SKIP review agent (SKIP_REVIEW=1)"
    else
        echo
        echo ">>> REVIEW AGENT (conditional): independent code review required"
        REPO_ROOT="$(cd "$HERE/../../../.." && pwd)"
        PARENT="$(git -C "$REPO_ROOT" rev-parse HEAD~1 2>/dev/null || echo "<parent>")"
        HEAD="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "<head>")"
        echo "Review diff: $PARENT..$HEAD"
        echo "Scope: src/plugins/rv-packages/layer_select/*.py (exclude golden-mac/)"
        echo "Spawn a FRESH generalPurpose agent — see VERIFICATION.md (Final review gate)."
        echo "Blocking findings → fix, then re-run ./run_migration_loop_mac.sh"
        git -C "$REPO_ROOT" diff --name-only "$PARENT" HEAD -- \
            'src/plugins/rv-packages/layer_select/*.py' 2>/dev/null || true
    fi
fi

echo
echo ">>> GATE 3 (MANDATORY): Default launch — behavioral, no RV_MODE_IMPL override"
if ! GATE=default "$HERE/run_all_goldens_mac.sh"; then
    echo "GATE 3 FAILED — fix mode registration / PACKAGE / preload wiring."
    exit 1
fi

echo
echo ">>> GATE 4 (MANDATORY): Mu baseline integrity — IMPL=mu vs golden-mac"
if ! GATE=both IMPL=mu "$HERE/run_all_goldens_mac.sh"; then
    echo "GATE 4 FAILED — harness or golden-mac corrupted; re-capture if Mu changed."
    exit 1
fi

echo
echo "=============================================="
if [ "${SKIP_PIXEL_GATE:-0}" = "1" ]; then
    echo "MIGRATION LOOP PASSED (Gates 0,1,3,4; Gate 2 pixel mismatch accepted)"
else
    echo "MIGRATION LOOP PASSED (all 5 mandatory gates)"
fi
echo "Confirm: sanity pixel review + code review (no blocking findings)."
echo "Update COVERAGE.md; ask user about removing layer_select_mode.mu."
echo "=============================================="
