#!/usr/bin/env bash
# Full migration loop — layer_select (Linux, golden/ under Xvfb).
# Same gate order as run_migration_loop_mac.sh — see ../VERIFICATION.md
# On blockers, keep working until unblocked (VERIFICATION.md § "When you hit a blocker").
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKIP_SANITY="${SKIP_SANITY:-0}"
SKIP_REVIEW="${SKIP_REVIEW:-0}"

echo "=============================================="
echo "layer_select migration loop (Linux)"
echo "See: $(cd "$HERE/../../../.." && pwd)/src/test/golden/VERIFICATION.md"
echo "=============================================="

if [ ! -d "$HERE/golden/ls_activate" ]; then
    echo "FAIL: no golden/ baselines — run ./capture_golden.sh first"
    exit 2
fi

echo ">>> GATE 0 (MANDATORY): Runtime clean"
if ! GATE=runtime IMPL=python "$HERE/run_all_goldens.sh"; then exit 1; fi

echo ">>> GATE 1 (MANDATORY): Behavioral"
if ! GATE=behavioral IMPL=python "$HERE/run_all_goldens.sh"; then exit 1; fi

echo ">>> GATE 2 (MANDATORY): Pixel"
if ! GATE=pixel IMPL=python "$HERE/run_all_goldens.sh"; then exit 1; fi

echo ">>> Gates 1+2 PASSED"
if [ "$SKIP_SANITY" != "1" ]; then
    echo "NOTE: Linux GUI sanity not wired — use NO_XVFB=1 smoke if needed."
fi
if [ "$SKIP_REVIEW" != "1" ]; then
    echo ">>> REVIEW AGENT: see VERIFICATION.md (Final review gate)"
fi

echo ">>> GATE 3 (MANDATORY): Default launch"
if ! GATE=default "$HERE/run_all_goldens.sh"; then exit 1; fi

echo ">>> GATE 4 (MANDATORY): Mu baseline integrity"
if ! GATE=both IMPL=mu "$HERE/run_all_goldens.sh"; then exit 1; fi

echo "MIGRATION LOOP PASSED"
