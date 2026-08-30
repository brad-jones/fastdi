#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Runs `cog check`, tolerating a repository that has no tags yet.

NB: cog.toml sets `from_latest_tag = true`, so plain `cog check` always scopes to commits since the
latest SemVer tag - even without passing `-l`/`--from-latest-tag` explicitly. Before this repo's first
release there is no tag to scope from, so cog exits with "unable to get any tag" instead of falling
back to checking the whole history.

Detect that specific failure and re-run `cog check` over an explicit `..` range, which walks the full
commit history and sidesteps the from-latest-tag default. Once a first release exists, plain `cog check`
succeeds and this fallback never triggers.
"""

import subprocess
import sys


def main() -> None:
  result = subprocess.run(["cog", "check"], capture_output=True, text=True, check=False)
  if result.returncode == 0:
    print(result.stdout, end="")
    return

  combined = result.stdout + result.stderr
  if "unable to get any tag" not in combined:
    print(combined, file=sys.stderr)
    sys.exit(result.returncode)

  print("no tags yet, checking the full commit history instead.")
  full_history = subprocess.run(["cog", "check", ".."], check=False)
  sys.exit(full_history.returncode)


if __name__ == "__main__":
  main()
