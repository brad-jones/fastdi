#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""A wrapper around the sops command that adds a few extra convenience commands that
provide a really simple key-value style interface to a set of repo wide secrets.
Check them out: get, set & rm

While sops itself supports a wide variety of encryption backends, this wrapper is
designed to work with age encryption to keep things vendor neutral and simple.

read more: https://getsops.io/
also: https://age-encryption.org/
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_CONFIG_FILE = SCRIPT_DIR.parent / ".sops.yaml"
REPO_SECRETS_FILE = SCRIPT_DIR.parent / ".sops.secrets.yaml"
DEFAULT_AGE_KEY_FILE = SCRIPT_DIR.parent / ".sops.age.key"
PUBLIC_KEY_RE = re.compile(r"public key: (age1[a-z0-9]+)")


def resolve_age_key_file() -> str | None:
  env_key_file = os.environ.get("SOPS_AGE_KEY_FILE")
  if env_key_file:
    return env_key_file
  return str(DEFAULT_AGE_KEY_FILE) if DEFAULT_AGE_KEY_FILE.exists() else None


def sops_env(age_key_file: str | None) -> dict[str, str]:
  env = os.environ.copy()
  if age_key_file:
    env["SOPS_AGE_KEY_FILE"] = age_key_file
  else:
    env.pop("SOPS_AGE_KEY_FILE", None)
  return env


def cmd_get(key: str, age_key_file: str | None) -> None:
  if not REPO_SECRETS_FILE.exists():
    print(f"No secrets file found at {REPO_SECRETS_FILE}", file=sys.stderr)
    sys.exit(1)

  result = subprocess.run(
    ["sops", "decrypt", str(REPO_SECRETS_FILE), "--extract", f'["{key}"]'],
    env=sops_env(age_key_file),
    capture_output=True,
    text=True,
    check=False,
  )
  if result.returncode != 0:
    print((result.stdout + result.stderr).strip(), file=sys.stderr)
    sys.exit(result.returncode)

  # NB: It's important we strip the result here as sops will return a trailing
  # newline which can cause issues when using the value in other commands.
  print(result.stdout.strip())


def cmd_set(key: str, value: str, age_key_file: str | None) -> None:
  # Handle the initial case where there is no sops config file.
  if not REPO_CONFIG_FILE.exists():
    print("No sops config found. How would you like to set up age encryption?")
    choice = input("  [1] Generate a new age key\n  [2] Provide an existing age key\nChoice [1]: ").strip() or "1"

    if choice == "1":
      result = subprocess.run(["age-keygen"], capture_output=True, text=True, check=True)
      output = result.stdout + result.stderr

      match = PUBLIC_KEY_RE.search(output)
      if not match:
        print("Failed to parse public key from age-keygen output", file=sys.stderr)
        sys.exit(1)
      public_key = match.group(1)

      DEFAULT_AGE_KEY_FILE.write_text(output)
      age_key_file = str(DEFAULT_AGE_KEY_FILE)
      print("Age key pair generated and saved to .sops.age.key")
    else:
      key_path = input("Enter the path to your existing age key file: ").strip()
      key_content = Path(key_path).read_text()

      match = PUBLIC_KEY_RE.search(key_content)
      if not match:
        print("Could not find public key in the provided key file.", file=sys.stderr)
        print("Expected a comment line like: # public key: age1...", file=sys.stderr)
        sys.exit(1)
      public_key = match.group(1)

      save_to_repo = input("Would you like to save this key to the repo as .sops.age.key? [Y/n]: ").strip() or "y"
      if save_to_repo.lower().startswith("y"):
        DEFAULT_AGE_KEY_FILE.write_text(key_content)
        age_key_file = str(DEFAULT_AGE_KEY_FILE)
        print("Key saved to .sops.age.key")
      else:
        age_key_file = key_path
        print("Hint: set the env var SOPS_AGE_KEY_FILE or SOPS_AGE_KEY at decryption time.")

    # Write the sops config file with the public key.
    REPO_CONFIG_FILE.write_text(f"# spec: https://getsops.io/docs/#using-sopsyaml-conf-to-select-kms-pgp-and-age-for-new-files\n\ncreation_rules:\n  - age: {public_key}\n")
    print("Sops config written to .sops.yaml")

  # Handle the initial case where there is no secrets file.
  if not REPO_SECRETS_FILE.exists():
    subprocess.run(
      ["sops", "encrypt", "--filename-override", REPO_SECRETS_FILE.name, "--output", str(REPO_SECRETS_FILE)],
      input=json.dumps({}),
      text=True,
      check=True,
    )

  # Once the sops metadata is written we can set values in the file.
  subprocess.run(
    ["sops", "set", str(REPO_SECRETS_FILE), f'["{key}"]', json.dumps(value)],
    env=sops_env(age_key_file),
    check=True,
  )


def cmd_rm(key: str, age_key_file: str | None) -> None:
  if not REPO_SECRETS_FILE.exists():
    print(f"No secrets file found at {REPO_SECRETS_FILE}", file=sys.stderr)
    sys.exit(1)

  subprocess.run(
    ["sops", "unset", str(REPO_SECRETS_FILE), f'["{key}"]'],
    env=sops_env(age_key_file),
    check=True,
  )


def main() -> None:
  argv = sys.argv[1:]
  age_key_file = resolve_age_key_file()

  if argv and argv[0] in {"get", "set", "rm"}:
    sub_cmd = argv[0]
    parser = argparse.ArgumentParser(prog=f"sops.py {sub_cmd}")
    parser.add_argument("-k", "--key", required=True, help="The secret key")
    if sub_cmd == "set":
      parser.add_argument("-v", "--value", required=True, help="The value of the secret")
    args = parser.parse_args(argv[1:])

    if sub_cmd == "get":
      cmd_get(args.key, age_key_file)
    elif sub_cmd == "set":
      cmd_set(args.key, args.value, age_key_file)
    else:
      cmd_rm(args.key, age_key_file)
    return

  if not argv:
    print(__doc__)
    sys.exit(1)

  # Any other sub-command is passed straight through to the real sops binary.
  result = subprocess.run(["sops", *argv], env=sops_env(age_key_file), check=False)
  sys.exit(result.returncode)


if __name__ == "__main__":
  main()
