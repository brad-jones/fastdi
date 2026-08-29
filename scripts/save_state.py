#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Snapshots the current working tree so it can later be restored by restore_state.py."""

import json
import subprocess
from pathlib import Path

STATE_FILE_NAME = "save-state.json"


def git_dir() -> Path:
  result = subprocess.run(["git", "rev-parse", "--git-dir"], check=True, capture_output=True, text=True)
  return Path(result.stdout.strip())


def main() -> None:
  is_dirty = bool(subprocess.run(["git", "status", "--porcelain"], check=True, capture_output=True, text=True).stdout.strip())

  # Snapshot the working tree (including untracked files) so it can be restored exactly
  # if verification fails later. `stash apply` immediately restores the snapshot to the
  # working tree, keeping it in the stash list as a backup.
  if is_dirty:
    subprocess.run(["git", "stash", "push", "--include-untracked", "-m", "save-state-backup"], check=True)
    subprocess.run(["git", "stash", "apply", "stash@{0}"], check=True)

  (git_dir() / STATE_FILE_NAME).write_text(json.dumps({"stashed": is_dirty}))


if __name__ == "__main__":
  main()
