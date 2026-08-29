#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Extracts the most recent changelog entry from cocogitto's full changelog output.

Useful when you have a monorepo with many packages and want to create GitHub
releases with just the changelog for a specific package.
"""

import sys


def main() -> None:
    content = sys.stdin.read()
    entry = content.split("- - -")[1].strip()
    sys.stdout.write(entry + "\n")


if __name__ == "__main__":
    main()
