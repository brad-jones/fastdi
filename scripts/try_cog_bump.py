#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Bumps the version with cocogitto, skipping cleanly when there is nothing to release.

NB: cocogitto has a quirk where, if HEAD is exactly the commit that was just tagged (e.g.
this workflow is re-run without any new commits having landed since the last release), it
still treats that tag's own "chore(version): vX.Y.Z" commit as an unreleased commit and
bumps again.
see: https://github.com/cocogitto/cocogitto/blob/main/crates/cocogitto/src/git/rev/revwalk.rs#L120-L125

Guard against this by skipping the bump entirely when HEAD is already an exact tag match,
since there's nothing new to release in that case.
"""

import subprocess
import sys


def main() -> None:
  exact_tag = subprocess.run(
    ["git", "describe", "--tags", "--exact-match", "HEAD"],
    capture_output=True,
    text=True,
    check=False,
  )
  if exact_tag.returncode == 0:
    print(f"nothing to do, HEAD is already released as {exact_tag.stdout.strip()}.")
    return

  dry_run = subprocess.run(["cog", "bump", "-d", "--skip-untracked", "--auto"], capture_output=True, text=True, check=False)
  combined = dry_run.stdout + dry_run.stderr
  if dry_run.returncode > 0:
    if "cause: No conventional commit found to bump current version." in combined:
      print("nothing to do, no conventional commit found to bump current version.")
      return
    print(combined, file=sys.stderr)
    sys.exit(dry_run.returncode)

  result = subprocess.run(["cog", "bump", "--auto"], check=False)
  sys.exit(result.returncode)


if __name__ == "__main__":
  main()
