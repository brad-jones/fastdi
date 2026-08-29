#!/bin/bash
set -euo pipefail

# Only run on Claude Code Remote sessions
# Direnv will handle the local environment setup.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install pixi if not already installed.
# We use the double check to avoid polluting the PATH with duplicates.
if ! command -v pixi >/dev/null 2>&1; then
  export PATH="$HOME/.pixi/bin:$PATH"
  if ! command -v pixi >/dev/null 2>&1; then
    export PIXI_NO_PATH_UPDATE=1
    curl -fsSL https://pixi.sh/install.sh | sh
  fi
fi

# Ensure that the pixi bin directory is in the PATH for all shells Claude Code starts.
if [ -n "${CLAUDE_ENV_FILE:-}" ] && ! grep -qs '.pixi/bin' "$CLAUDE_ENV_FILE"; then
  echo 'export PATH="$HOME/.pixi/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi

# Activate the pixi environment for all shells Claude Code starts, mirroring .envrc's direnv setup.
if [ -n "${CLAUDE_ENV_FILE:-}" ] && ! grep -qs '# pixi shell-hook' "$CLAUDE_ENV_FILE"; then
  {
    echo '# pixi shell-hook'
    pixi shell-hook --shell bash
  } >> "$CLAUDE_ENV_FILE"
fi

APM_TARGET=claude pixi run task init
