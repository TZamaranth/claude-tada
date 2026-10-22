#!/bin/bash
# Browse, preview and pick tada sounds.
#
#   tada.sh list                              every sound, with a description
#   tada.sh show                              what plays for each event right now
#   tada.sh play <name>                       preview a sound
#   tada.sh set <done|needs-input> <choice>   choice: a sound name, random, off or default
#
# Choices are saved in ~/.claude/tada.conf and apply to the next hook, no restart.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

fail() {
  echo "tada: $1" >&2
  exit 1
}

list_sound_group() {
  local group_name="$1" heading="$2"
  echo "$heading"
  awk -F'\t' -v group="$group_name" '
    { sub(/\r$/, "") }
    $4 == group { printf "  %-26s %-13s %s\n", $1, ($2 == "nudge" ? "[needs-input]" : "[done]"), $3 }
  ' "$TADA_CATALOG"
  echo
}

list_sounds() {
  list_sound_group synth "Chimes and synths:"
  list_sound_group recording "Real-world sounds:"
  list_sound_group voice "Voices:"
  echo "[done] / [needs-input] is the suggested event; any sound works for either."
  echo "Also: random (a different one each time), off (silent)."
}

describe_event_setting() {
  local event_name="$1" override_file choice
  override_file="$(user_override_file "$event_name")"
  if [ -n "$override_file" ]; then
    echo "your own file $override_file"
    return
  fi
  choice="$(configured_choice "$event_name")"
  if [ -z "$choice" ]; then
    echo "$(default_sound_name "$event_name") (default)"
    return
  fi
  if [ "$choice" != random ] && [ "$choice" != off ] && ! is_library_sound "$choice"; then
    echo "$choice (unknown name, so the default $(default_sound_name "$event_name") plays)"
    return
  fi
  echo "$choice"
}

show_settings() {
  for event_name in $TADA_EVENTS; do
    printf '%-12s %s\n' "$event_name:" "$(describe_event_setting "$event_name")"
  done
}

play_named_sound() {
  local sound_name="$1"
  [ -n "$sound_name" ] || fail "usage: tada.sh play <name>  (see: tada.sh list)"
  is_library_sound "$sound_name" || fail "no sound named '$sound_name' (see: tada.sh list)"
  bash "$TADA_SCRIPT_DIR/play-file.sh" "$TADA_LIBRARY_DIR/$sound_name.wav"
}

# Rewrites tada.conf without the event's line, then appends the new choice (unless resetting).
save_choice() {
  local event_name="$1" choice="$2" kept_lines=""
  mkdir -p "$(dirname "$TADA_SETTINGS_FILE")"
  if [ -f "$TADA_SETTINGS_FILE" ]; then
    kept_lines="$(grep -v -E "$(event_line_pattern "$event_name")" "$TADA_SETTINGS_FILE" | tr -d '\r')"
  fi
  {
    [ -n "$kept_lines" ] && echo "$kept_lines"
    [ "$choice" != default ] && echo "$event_name=$choice"
  } >"$TADA_SETTINGS_FILE.tmp"
  mv "$TADA_SETTINGS_FILE.tmp" "$TADA_SETTINGS_FILE"
}

set_choice() {
  local event_name="$1" choice="$2"
  is_known_event "$event_name" || fail "usage: tada.sh set <done|needs-input> <name|random|off|default>"
  case "$choice" in
    random|off|default) ;;
    *) is_library_sound "$choice" || fail "no sound named '$choice' (see: tada.sh list)" ;;
  esac
  save_choice "$event_name" "$choice"
  echo "$event_name: $(describe_event_setting "$event_name")"
  local override_file
  override_file="$(user_override_file "$event_name")"
  if [ -n "$override_file" ]; then
    echo "note: your own file $override_file still wins; delete it to use this choice"
  fi
}

case "${1:-}" in
  list) list_sounds ;;
  show) show_settings ;;
  play) play_named_sound "${2:-}" ;;
  set) set_choice "${2:-}" "${3:-}" ;;
  *) fail "usage: tada.sh list | show | play <name> | set <done|needs-input> <name|random|off|default>" ;;
esac
