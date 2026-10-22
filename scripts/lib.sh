#!/bin/bash
# Shared lookups for play-sound.sh and tada.sh. Source it; don't run it.
#
# Which file plays for an event (done, needs-input), first match wins:
#   1. your own file:  ~/.claude/sounds/<event>.{mp3,wav,m4a,aiff,ogg}
#   2. your choice:    ~/.claude/tada.conf line "<event>=<sound name|random|off>"
#   3. the default:    tada for done, hm for needs-input
#
# A sound name is a bundled sounds/<name>.wav, or a clip you added with
# "tada.sh add <file>", kept as ~/.claude/sounds/<name>.{mp3,wav,m4a}.
# Bundled names win, and "add" refuses them, so the two never collide.

TADA_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TADA_LIBRARY_DIR="$(dirname "$TADA_SCRIPT_DIR")/sounds"
TADA_CATALOG="$TADA_LIBRARY_DIR/catalog.tsv"
TADA_USER_SOUNDS_DIR="$HOME/.claude/sounds"
TADA_SETTINGS_FILE="$HOME/.claude/tada.conf"
TADA_EVENTS="done needs-input"
TADA_ADDED_EXTENSIONS="mp3 wav m4a" # formats every supported OS can play

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

# Sound names are lowercase letters, digits and dashes, so a name can't reach outside its folder.
is_valid_name() {
  case "$1" in
    ""|*[!a-z0-9-]*) return 1 ;;
    *) return 0 ;;
  esac
}

is_bundled_sound() {
  is_valid_name "$1" && [ -f "$TADA_LIBRARY_DIR/$1.wav" ]
}

# Prints the file of a clip the user added under this name, or nothing.
# done and needs-input are never added clips: files with those names are event overrides.
added_sound_file() {
  local sound_name="$1" extension
  is_valid_name "$sound_name" || return 0
  is_known_event "$sound_name" && return 0
  for extension in $TADA_ADDED_EXTENSIONS; do
    if [ -f "$TADA_USER_SOUNDS_DIR/$sound_name.$extension" ]; then
      echo "$TADA_USER_SOUNDS_DIR/$sound_name.$extension"
      return
    fi
  done
}

# Prints the name of every clip the user added, one per line, sorted.
added_sound_names() {
  local extension clip sound_name
  for extension in $TADA_ADDED_EXTENSIONS; do
    for clip in "$TADA_USER_SOUNDS_DIR"/*."$extension"; do
      [ -f "$clip" ] || continue
      sound_name="$(basename "$clip" ".$extension")"
      is_valid_name "$sound_name" || continue
      is_known_event "$sound_name" && continue
      is_bundled_sound "$sound_name" && continue
      echo "$sound_name"
    done
  done | sort -u
}

# Prints the file for a sound name (bundled first, then added clips), or nothing.
sound_file() {
  local sound_name="$1"
  if is_bundled_sound "$sound_name"; then
    echo "$TADA_LIBRARY_DIR/$sound_name.wav"
    return
  fi
  added_sound_file "$sound_name"
}

is_library_sound() {
  [ -n "$(sound_file "$1")" ]
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

# Any bundled sound or added clip.
random_library_file() {
  local library_files=("$TADA_LIBRARY_DIR"/*.wav) sound_name
  while IFS= read -r sound_name; do
    library_files+=("$(added_sound_file "$sound_name")")
  done < <(added_sound_names)
  echo "${library_files[RANDOM % ${#library_files[@]}]}"
}
