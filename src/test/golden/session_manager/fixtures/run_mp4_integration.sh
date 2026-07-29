#!/usr/bin/env bash
# Run session_manager MP4 integration scenarios.
#
# Requires SM_TEST_MP4_DIR (directory of *.mp4 clips).  Optional local config:
#   cp mp4.env.example mp4.env   # edit paths, never commit mp4.env
#
# Other env vars:
#   SM_TEST_MP4_FIXTURE   single file for sm_mp4_load.py
#   RV                    path to rv launcher (default: staged build)
#   IMPL                  mu or python (default: python)
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../../../.." && pwd)"
RUNNER="$REPO_ROOT/src/test/golden/harness/run_scenario.py"
RV="${RV:-$REPO_ROOT/_build/stage/app/bin/rv}"

if [ -f "$HERE/mp4.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$HERE/mp4.env"
    set +a
fi

if [ -z "${SM_TEST_MP4_DIR:-}" ]; then
    echo "ERROR: SM_TEST_MP4_DIR is not set." >&2
    echo "  export SM_TEST_MP4_DIR=/path/to/mp4/clips" >&2
    echo "  or: cp $HERE/mp4.env.example $HERE/mp4.env && edit mp4.env" >&2
    exit 2
fi

if [ ! -d "$SM_TEST_MP4_DIR" ]; then
    echo "ERROR: SM_TEST_MP4_DIR is not a directory: $SM_TEST_MP4_DIR" >&2
    exit 2
fi

clip_count="$(find "$SM_TEST_MP4_DIR" -maxdepth 1 -name '*.mp4' | wc -l)"
echo "SM_TEST_MP4_DIR: $SM_TEST_MP4_DIR ($clip_count clips)"

fail=0

run_one() {
    local scenario="$1"
    local out="$2"
    local timeout="$3"
    local impl="${IMPL:-python}"
    rm -rf "$out"
    mkdir -p "$out"
    echo "==> $(basename "$scenario") -> $out (timeout ${timeout}s, --impl $impl)"
    # Guarded (not a bare call): under set -e, sm_mp4_load timing out/crashing
    # would otherwise abort this script before sm_mp4_all -- the actual point
    # of this integration run, and potentially a multi-hour job -- ever ran
    # at all, with no message explaining why (same bug found and fixed
    # 2026-07-24 in capture_golden.sh / capture_golden_mac.sh).
    if ! python3 "$RUNNER" \
        --scenario "$scenario" \
        --out "$out" \
        --rv "$RV" \
        --impl "$impl" \
        --timeout "$timeout"; then
        echo "FAIL: $(basename "$scenario") (run_scenario exited non-zero -- timeout or crash)"
        fail=$((fail + 1))
    fi
    if [ -f "$out/diag.txt" ]; then
        echo "--- diag.txt ---"
        tail -20 "$out/diag.txt"
    fi
}

run_one \
    "$REPO_ROOT/src/test/golden/session_manager/scenarios/sm_mp4_load.py" \
    "${OUT:-/tmp/sm_mp4_load}" \
    "${TIMEOUT_SINGLE:-600}"

run_one \
    "$REPO_ROOT/src/test/golden/session_manager/scenarios/sm_mp4_all.py" \
    "${OUT_ALL:-/tmp/sm_mp4_all}" \
    "${TIMEOUT_ALL:-7200}"

if [ "$fail" -gt 0 ]; then
    echo "Done, with $fail failure(s)."
    exit 1
fi
echo "Done."
