#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Restores the executable bit on staged scripts, since git doesn't always preserve it."""

import os
import re
import subprocess

STAGE_LINE_RE = re.compile(r"^\d+\s[a-f0-9]+\s\d+\s+(.*)$")
WATCHED_DIRS = ("scripts/", ".lefthook/", ".claude/hooks/")


def main() -> None:
  lines = subprocess.run(["git", "ls-files", "--stage"], check=True, capture_output=True, text=True).stdout.splitlines()

  for line in lines:
    if not any(watched in line for watched in WATCHED_DIRS):
      continue
    if not line.startswith("100644"):
      continue
    match = STAGE_LINE_RE.match(line)
    if not match:
      continue

    file = match.group(1)
    if os.name == "nt":
      subprocess.run(["git", "update-index", "--add", "--chmod=+x", file], check=True)
    else:
      os.chmod(file, 0o755)


if __name__ == "__main__":
  main()
