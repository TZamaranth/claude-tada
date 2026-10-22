#!/bin/bash
# Plays one audio file with whatever player this OS has. Usage: play-file.sh <path>
# Falls back to a terminal bell when there is no player or no file.

SOUND_FILE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SOUND_FILE" ]; then
  echo "play-file.sh: sound file not found: $SOUND_FILE" >&2
  printf '\a'
  exit 0
fi

play_on_linux() {
  local players="paplay pw-play aplay"
  # aplay reads only WAV; given an mp3 it plays loud static, so leave it out.
  case "$SOUND_FILE" in
    *.wav|*.WAV) ;;
    *) players="paplay pw-play" ;;
  esac
  for player in $players; do
    if command -v "$player" >/dev/null 2>&1 && "$player" "$SOUND_FILE" 2>/dev/null; then
      return 0
    fi
  done
  if command -v ffplay >/dev/null 2>&1; then
    ffplay -nodisp -autoexit -loglevel quiet "$SOUND_FILE" && return 0
  fi
  return 1
}

case "$(uname -s)" in
  Darwin)
    afplay "$SOUND_FILE" || printf '\a'
    ;;
  Linux)
    play_on_linux || printf '\a'
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
