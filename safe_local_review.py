#!/usr/bin/env python3
"""Passive local security review for Python projects.

This tool only reads source files from a local directory. It does not make
network requests, submit payloads, test logins, enumerate endpoints, or access
remote systems. Findings are heuristic and require manual review.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules",
    "dist", "build", ".mypy_cache", ".pytest_cache",
}
MAX_FILE_BYTES = 1_000_000

RULES = [
    (
        "HIGH",
        "TLS verification disabled",
        re.compile(r"\bverify\s*=\s*False\b|_create_unverified_context\s*\("),
        "Use normal certificate verification; configure a trusted CA when needed.",
    ),
    (
        "MEDIUM",
        "Debug mode enabled",
        re.compile(r"\bdebug\s*=\s*True\b"),
        "Disable debug mode in deployed environments.",
    ),
    (
        "HIGH",
        "Possible hard-coded secret",
        re.compile(
            r"""(?i)\b(?:api[_-]?key|secret|password|passwd|access[_-]?token)\b"""
            r"""\s*[:=]\s*["'][^"']{6,}["']"""
        ),
        "Move secrets to a secure environment/configuration store and rotate exposed values.",
    ),
]


def iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
                yield path
        except OSError:
            continue


def review(root: Path):
    findings = []
    for path in iter_python_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            for severity, title, pattern, advice in RULES:
                if pattern.search(line):
                    # Never print the matched line: it may contain a secret.
                    findings.append((severity, path.relative_to(root), number, title, advice))
    return findings


def main():
    parser = argparse.ArgumentParser(
        description="Passively inspect local Python source for a few common security misconfigurations."
    )
    parser.add_argument("directory", nargs="?", default=".", help="Local project directory (default: current directory)")
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    if not root.is_dir():
        parser.error("directory does not exist or is not a directory")

    findings = review(root)
    print("XEBAC HYBRID v2 — SAFE LOCAL REVIEW")
    print(f"Directory: {root}")
    print("Mode: local, read-only, passive (no network activity)")
    print()
    if not findings:
        print("No matching patterns found. This is not proof that the project is secure.")
        return 0

    for severity, path, line, title, advice in findings:
        print(f"[{severity}] {path}:{line} — {title}")
        print(f"  Recommendation: {advice}")
    print()
    print(f"{len(findings)} potential finding(s). Review each result manually; false positives are possible.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
