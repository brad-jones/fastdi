#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Runs the given verification commands, restoring the snapshot taken by save_state.py if any of them fail."""

import argparse
import json
import subprocess
import sys

from save_state import STATE_FILE_NAME, git_dir


def revert(stashed: bool) -> None:
    print("restore-state: verification failed, reverting changes...", file=sys.stderr)
    subprocess.run(["git", "reset", "--hard", "HEAD"], check=False)
    subprocess.run(["git", "clean", "-fd"], check=False)
    if stashed:
        subprocess.run(["git", "stash", "pop", "stash@{0}"], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Runs the given verification commands, restoring the snapshot taken by "
        "save_state.py if any of them fail."
    )
    parser.add_argument(
        "--verify-with",
        action="append",
        required=True,
        help="A command to run to verify the changes made since save_state.py. Can be given multiple times.",
    )
    args = parser.parse_args()

    state_file = git_dir() / STATE_FILE_NAME
    stashed = json.loads(state_file.read_text())["stashed"]

    for command in args.verify_with:
        result = subprocess.run(command, shell=True, check=False)
        if result.returncode != 0:
            revert(stashed)
            state_file.unlink()
            sys.exit(result.returncode)

    # Everything passed, so the pre-fix snapshot is no longer needed.
    if stashed:
        subprocess.run(["git", "stash", "drop", "stash@{0}"], check=True)
    state_file.unlink()
    print("restore-state: fixes verified successfully.")


if __name__ == "__main__":
    main()
