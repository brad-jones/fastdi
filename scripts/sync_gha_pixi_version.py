#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Syncs the pinned Pixi version in GitHub Actions workflows with the locally installed Pixi version.

NB: This assumes it has been run directly after running `pixi self-update`.
"""

import re
import subprocess
from pathlib import Path

DIFF_FILE = Path("diff.md")
WORKFLOWS_DIR = Path(".github/workflows")
PIXI_VERSION_RE = re.compile(r"pixi-version:\s*v\d+\.\d+\.\d+")


def main() -> None:
  version_output = subprocess.run(["pixi", "--version"], check=True, capture_output=True, text=True).stdout
  match = re.match(r"^pixi\s+(\d+\.\d+\.\d+)", version_output.strip())
  if not match:
    raise SystemExit(f"Could not parse pixi version from: {version_output}")
  version_tag = f"v{match.group(1)}"

  # Update all GHA workflows in `.github/workflows` to use that version of Pixi.
  version_changed = False
  for file in sorted(WORKFLOWS_DIR.iterdir()):
    if not file.is_file() or file.suffix not in (".yaml", ".yml"):
      continue

    original = file.read_text()
    updated = PIXI_VERSION_RE.sub(f"pixi-version: {version_tag}", original)
    if updated != original:
      file.write_text(updated)
      print(f"updated pixi version in {file} to {version_tag}")
      version_changed = True

  # When run as part of the `update` GitHub Actions workflow, a `diff.md` file is
  # generated from `pixi update --json` to describe the lockfile changes in the resulting
  # PR. If that file exists and the pinned Pixi version actually changed, append a note
  # about the Pixi self-update so it's reflected in the PR body too.
  if version_changed and DIFF_FILE.exists():
    note = f"\n## Pixi\n\nUpdated Pixi to `{version_tag}`.\n"
    with DIFF_FILE.open("a") as f:
      f.write(note)
    print(f"updated {DIFF_FILE} with Pixi self-update note")


if __name__ == "__main__":
  main()
