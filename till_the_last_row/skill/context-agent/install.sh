#!/usr/bin/env bash
#
# Installer for the `context-agent` skill.
#
# Copies this skill folder into an agent's skills directory so it is auto-loaded.
# Works for opencode and for Claude Code / agents-style skill locations.
#
# Usage:
#   ./install.sh                 # install for opencode (global): ~/.config/opencode/skills
#   ./install.sh --target claude # install for Claude Code:       ~/.claude/skills
#   ./install.sh --target agents # install for ~/.agents/skills
#   ./install.sh --dir /path     # install into an explicit skills directory
#   ./install.sh --project       # install into ./.opencode/skills (current repo)
#
set -euo pipefail

SKILL_NAME="context-agent"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET="opencode"
EXPLICIT_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --dir)    EXPLICIT_DIR="$2"; shift 2 ;;
    --project) TARGET="project"; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [ -n "$EXPLICIT_DIR" ]; then
  DEST_ROOT="$EXPLICIT_DIR"
else
  case "$TARGET" in
    opencode) DEST_ROOT="${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills" ;;
    claude)   DEST_ROOT="$HOME/.claude/skills" ;;
    agents)   DEST_ROOT="$HOME/.agents/skills" ;;
    project)  DEST_ROOT="$PWD/.opencode/skills" ;;
    *) echo "Unknown --target '$TARGET' (use opencode|claude|agents|project)" >&2; exit 1 ;;
  esac
fi

DEST="$DEST_ROOT/$SKILL_NAME"

echo "Installing '$SKILL_NAME'"
echo "  from: $SRC_DIR"
echo "  to:   $DEST"

mkdir -p "$DEST_ROOT"

if [ -e "$DEST" ]; then
  echo "  note: $DEST already exists — replacing it"
  rm -rf "$DEST"
fi

mkdir -p "$DEST"
# Copy the skill payload but never the installer itself.
for item in SKILL.md references; do
  if [ -e "$SRC_DIR/$item" ]; then
    cp -R "$SRC_DIR/$item" "$DEST/"
  fi
done

echo "Done."
echo
echo "Next steps:"
echo "  1. Restart opencode (config & skills load once at startup)."
echo "  2. This skill is chained from 'design-ch-schema' (schema-change trigger),"
echo "     or trigger it directly, e.g.: \"a new table landed — update context\"."
