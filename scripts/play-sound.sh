#!/bin/bash
# Hook entry point: plays the sound chosen for an event. Usage: play-sound.sh done|needs-input
# See lib.sh for how the file is chosen. Never fails the hook.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

EVENT_NAME="${1:-done}"
if ! is_known_event "$EVENT_NAME"; then
  echo "play-sound.sh: unknown event '$EVENT_NAME' (expected done or needs-input)" >&2
  exit 0
fi

resolve_sound_file() {
  local override_file choice
  override_file="$(user_override_file "$EVENT_NAME")"
  if [ -n "$override_file" ]; then
    echo "$override_file"
    return
  fi
  choice="$(configured_choice "$EVENT_NAME")"
  case "$choice" in
    off) return ;;
    random) random_library_file; return ;;
    "") ;;
    *)
      if is_library_sound "$choice"; then
        sound_file "$choice"
        return
      fi
      echo "play-sound.sh: no sound named '$choice' in $TADA_SETTINGS_FILE; using the default" >&2
      ;;
  esac
  echo "$TADA_LIBRARY_DIR/$(default_sound_name "$EVENT_NAME").wav"
}

SOUND_FILE="$(resolve_sound_file)"
[ -z "$SOUND_FILE" ] && exit 0
bash "$TADA_SCRIPT_DIR/play-file.sh" "$SOUND_FILE"
exit 0
