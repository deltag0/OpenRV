#!/usr/bin/env python3
"""Fail golden runs when RV emitted runtime errors during a scenario."""

from __future__ import annotations

import os
import re
import sys
from typing import Iterable

_HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWLIST_PATH = os.path.join(_HERE, "runtime_error_allowlist.txt")

_ERROR_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Traceback \(most recent call last\)", re.I),
    re.compile(r"Exception thrown while calling", re.I),
    re.compile(r"runtime\.eval,\s*line\s+\d+", re.I),
    re.compile(r"Unresolved reference to", re.I),
    re.compile(r"Unable to reference", re.I),
    re.compile(r"Cannot use default constructor", re.I),
    re.compile(r"^Exception\s*:", re.I),
    re.compile(r"^TypeError\s*:", re.I),
    re.compile(r"^SyntaxError\s*:", re.I),
    re.compile(r"^ValueError\s*:", re.I),
    re.compile(r"^AttributeError\s*:", re.I),
    re.compile(r"^RuntimeError\s*:", re.I),
    re.compile(r"^Mu\s+exception\s*:", re.I),
)

_NEVER_ALLOW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"runtime\.eval", re.I),
    re.compile(r"Exception thrown while calling runtime\.eval", re.I),
)


def _load_allowlist() -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    if not os.path.isfile(ALLOWLIST_PATH):
        return patterns
    with open(ALLOWLIST_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(re.compile(line))
    return patterns


def _is_error_line(line: str) -> bool:
    return any(p.search(line) for p in _ERROR_LINE_PATTERNS)


def _extract_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_traceback = False

    for line in text.splitlines():
        if re.search(r"Traceback \(most recent call last\)", line, re.I):
            if current:
                blocks.append("\n".join(current))
            current = [line]
            in_traceback = True
            continue
        if in_traceback:
            current.append(line)
            # End traceback at blank line after content, or keep absorbing
            # exception type lines (TypeError: ...) that follow the stack.
            if line.strip() == "" and len(current) > 3:
                blocks.append("\n".join(current))
                current = []
                in_traceback = False
            continue
        if _is_error_line(line):
            blocks.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _never_allow(block: str) -> bool:
    return any(p.search(block) for p in _NEVER_ALLOW_PATTERNS)


def _block_allowlisted(block: str, allowlist: Iterable[re.Pattern[str]]) -> bool:
    if _never_allow(block):
        return False
    allow = list(allowlist)
    if not allow:
        return False
    return any(a.search(block) for a in allow)


def _is_violation(block: str, allowlist: list[re.Pattern[str]], package_markers: list[str] | None) -> bool:
    if _never_allow(block):
        return True
    if package_markers and any(m in block for m in package_markers):
        return True
    return not _block_allowlisted(block, allowlist)


def find_runtime_violations(
    rv_log_text: str,
    *,
    traceback_text: str | None = None,
    package_markers: list[str] | None = None,
) -> list[str]:
    allowlist = _load_allowlist()
    violations: list[str] = []
    reported: set[str] = set()

    def add(kind: str, block: str) -> None:
        key = kind + "\n" + block
        if key in reported:
            return
        reported.add(key)
        violations.append(f"{kind}:\n{block}")

    if traceback_text and traceback_text.strip():
        block = traceback_text.strip()
        if _is_violation(block, allowlist, package_markers):
            add("scenario traceback.txt", block)

    for block in _extract_blocks(rv_log_text):
        if _is_violation(block, allowlist, package_markers):
            add("RV log", block)

    return violations


def check_out_dir(out_dir: str, package_markers: list[str] | None = None) -> list[str]:
    rv_log = os.path.join(out_dir, "rv.log")
    tb_path = os.path.join(out_dir, "traceback.txt")
    rv_text = ""
    if os.path.isfile(rv_log):
        with open(rv_log, encoding="utf-8", errors="replace") as f:
            rv_text = f.read()
    tb_text = None
    if os.path.isfile(tb_path):
        with open(tb_path, encoding="utf-8", errors="replace") as f:
            tb_text = f.read()
    return find_runtime_violations(rv_text, traceback_text=tb_text, package_markers=package_markers)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: runtime_log_check.py OUT_DIR", file=sys.stderr)
        return 2
    violations = check_out_dir(sys.argv[1])
    if not violations:
        print("runtime: CLEAN")
        return 0
    print("runtime: FAIL")
    for v in violations:
        print("---")
        print(v)
    return 1


if __name__ == "__main__":
    sys.exit(main())
