#!/bin/bash
# fastReader wrapper (Linux/macOS). Thin dispatcher:
#   - load|toc|get|search -> python -m fastReader.<cmd> (PYTHONPATH auto-set)
#   - json               -> pass-through to the quick-json-reader binary
#                           when the sibling skill is installed
# All human-readable help text lives in:
#   wrapper_help_json_on.txt
#   wrapper_help_json_off.txt
# so that .sh and .bat share one source of truth and stay in sync.

set -e

# Use invocation path as-is so folder symlinks remain transparent
# (e.g. ~/.claude/skills/fastReader -> dev checkout). Do NOT call
# readlink -f here; that would collapse the symlink and move the
# json-probe out of the invoker's skills-root.
FAST_READER_WRAPPER_SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
FAST_READER_SKILL_PARENT_DIR="$(dirname "$FAST_READER_WRAPPER_SCRIPT_DIR")"

FAST_READER_DEFAULT_JSON_BIN_PATH="$FAST_READER_SKILL_PARENT_DIR/quick-json-reader/quick-json-reader"
FAST_READER_JSON_BIN_PATH="${FAST_READER_JSON_BIN:-$FAST_READER_DEFAULT_JSON_BIN_PATH}"

is_quick_json_reader_binary_available() {
  [ -x "$FAST_READER_JSON_BIN_PATH" ]
}

print_fast_reader_wrapper_help_text() {
  if is_quick_json_reader_binary_available; then
    cat "$FAST_READER_WRAPPER_SCRIPT_DIR/wrapper_help_json_on.txt"
  else
    cat "$FAST_READER_WRAPPER_SCRIPT_DIR/wrapper_help_json_off.txt"
  fi
}

if [ "$#" -lt 1 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  print_fast_reader_wrapper_help_text
  exit 0
fi

FAST_READER_SUBCOMMAND_NAME="$1"
shift

case "$FAST_READER_SUBCOMMAND_NAME" in
  load|toc|get|search)
    PYTHONPATH="$FAST_READER_SKILL_PARENT_DIR" exec python3 -m "fastReader.$FAST_READER_SUBCOMMAND_NAME" "$@"
    ;;
  json)
    if is_quick_json_reader_binary_available; then
      exec "$FAST_READER_JSON_BIN_PATH" "$@"
    else
      echo "fastReader: the 'json' module requires the quick-json-reader skill." >&2
      echo "Expected binary at: $FAST_READER_JSON_BIN_PATH" >&2
      echo "Install the quick-json-reader skill alongside fastReader, or set" >&2
      echo "FAST_READER_JSON_BIN to an absolute path to the binary." >&2
      exit 3
    fi
    ;;
  *)
    echo "fastReader: unknown subcommand '$FAST_READER_SUBCOMMAND_NAME'" >&2
    print_fast_reader_wrapper_help_text >&2
    exit 2
    ;;
esac
