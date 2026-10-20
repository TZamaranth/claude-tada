#!/bin/bash
# Plays a Claude Code event sound. Usage: play-sound.sh done|needs-input
#
# Lookup order for the sound file:
#   1. your own file: ~/.claude/sounds/<event>.{mp3,wav,m4a,aiff,ogg}
#   2. the bundled file: <plugin>/sounds/<event>.wav
# Never fails the hook: a missing player or file falls back to a terminal bell.

EVENT_NAME="${1:-done}"
case "$EVENT_NAME" in
  done|needs-input) ;;
  *)
    echo "play-sound.sh: unknown event '$EVENT_NAME' (expected done or needs-input)" >&2
    exit 0
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"
USER_SOUNDS_DIR="$HOME/.claude/sounds"

find_sound_file() {
  for extension in mp3 wav m4a aiff ogg; do
    if [ -f "$USER_SOUNDS_DIR/$EVENT_NAME.$extension" ]; then
      echo "$USER_SOUNDS_DIR/$EVENT_NAME.$extension"
      return
    fi
  done
  echo "$PLUGIN_DIR/sounds/$EVENT_NAME.wav"
}

play_on_linux() {
  local sound_file="$1"
  for player in paplay pw-play aplay; do
    if command -v "$player" >/dev/null 2>&1 && "$player" "$sound_file" 2>/dev/null; then
      return 0
    fi
  done
  if command -v ffplay >/dev/null 2>&1; then
    ffplay -nodisp -autoexit -loglevel quiet "$sound_file" && return 0
  fi
  return 1
}

SOUND_FILE="$(find_sound_file)"
if [ ! -f "$SOUND_FILE" ]; then
  echo "play-sound.sh: sound file not found: $SOUND_FILE" >&2
  printf '\a'
  exit 0
fi

case "$(uname -s)" in
  Darwin)
    afplay "$SOUND_FILE" || printf '\a'
    ;;
  Linux)
    play_on_linux "$SOUND_FILE" || printf '\a'
    ;;
  MINGW*|MSYS*|CYGWIN*)
    powershell.exe -NoProfile -ExecutionPolicy Bypass \
      -File "$(cygpath -w "$SCRIPT_DIR/play-sound.ps1")" "$(cygpath -w "$SOUND_FILE")" || printf '\a'
    ;;
  *)
    printf '\a'
    ;;
esac

exit 0
