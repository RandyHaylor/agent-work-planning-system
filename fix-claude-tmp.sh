#!/usr/bin/env bash
set -euo pipefail

claude_tmp_dir="${HOME}/.cache/claude-code/tmp"
shell_config="${HOME}/.bashrc"
export_line='export CLAUDE_CODE_TMPDIR="$HOME/.cache/claude-code/tmp"'

mkdir -p -- "$claude_tmp_dir"
chmod 700 -- "$claude_tmp_dir"

if [[ ! -O "$claude_tmp_dir" ]]; then
  echo "Error: $claude_tmp_dir is not owned by the current user." >&2
  exit 1
fi

touch -- "$shell_config"

if ! grep -Fqx -- "$export_line" "$shell_config"; then
  printf '\n%s\n' "$export_line" >> "$shell_config"
fi

echo "Claude temp directory fixed: $claude_tmp_dir"
echo "The setting was saved in: $shell_config"
echo "Run 'source ~/.bashrc' or open a new terminal before using Claude."
