#!/bin/bash
# Shared lookups for play-sound.sh and tada.sh. Source it; don't run it.
#
# Which file plays for an event (done, needs-input), first match wins:
#   1. your own file:  ~/.claude/sounds/<event>.{mp3,wav,m4a,aiff,ogg}
#   2. your choice:    ~/.claude/tada.conf line "<event>=<sound name|random|off>"
#   3. the default:    tada for done, hm for needs-input

TADA_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TADA_LIBRARY_DIR="$(dirname "$TADA_SCRIPT_DIR")/sounds"
TADA_CATALOG="$TADA_LIBRARY_DIR/catalog.tsv"
TADA_USER_SOUNDS_DIR="$HOME/.claude/sounds"
TADA_SETTINGS_FILE="$HOME/.claude/tada.conf"
TADA_EVENTS="done needs-input"

is_known_event() {
  case "$1" in
    done|needs-input) return 0 ;;
    *) return 1 ;;
  esac
}

default_sound_name() {
  case "$1" in
    needs-input) echo "hm" ;;
    *) echo "tada" ;;
  esac
}

is_library_sound() {
  [ -n "$1" ] && [ -f "$TADA_LIBRARY_DIR/$1.wav" ]
}

# Prints the path of the user's own file for an event, or nothing.
user_override_file() {
  local event_name="$1"
  for extension in mp3 wav m4a aiff ogg; do
    if [ -f "$TADA_USER_SOUNDS_DIR/$event_name.$extension" ]; then
      echo "$TADA_USER_SOUNDS_DIR/$event_name.$extension"
      return
    fi
  done
}

# Matches an event's line in tada.conf, tolerating spaces around "=".
event_line_pattern() {
  echo "^[[:space:]]*$1[[:space:]]*="
}

# Prints the value set in tada.conf for an event, or nothing.
configured_choice() {
  local event_name="$1"
  [ -f "$TADA_SETTINGS_FILE" ] || return 0
  grep -E "$(event_line_pattern "$event_name")" "$TADA_SETTINGS_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r[:space:]'
}

random_library_file() {
  local library_files=("$TADA_LIBRARY_DIR"/*.wav)
  echo "${library_files[RANDOM % ${#library_files[@]}]}"
}
