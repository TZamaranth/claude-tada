#!/bin/bash
(set -o igncr) 2>/dev/null && set -o igncr # tolerate Windows line endings (older Git Bash), no-op elsewhere
# Browse, preview and pick tada sounds, and add your own.
#
#   tada.sh list                              every sound, with a description
#   tada.sh show                              what plays for each event right now
#   tada.sh play <name>                       preview a sound
#   tada.sh set <done|needs-input> <choice>   choice: a sound name, random, off or default
#   tada.sh add <file> [name]                 add a clip you downloaded or recorded
#   tada.sh remove <name>                     delete a clip you added
#   tada.sh downloads                         your newest audio files in ~/Downloads
#
# Choices are saved in ~/.claude/tada.conf and apply to the next hook, no restart.
# Added clips are copied to ~/.claude/sounds/<name>.<mp3|wav|m4a>. tada never
# downloads anything: you get the clip, tada plays it.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

LONG_CLIP_BYTES=1000000 # roughly 5+ seconds of MP3, or 10+ seconds of WAV
MAX_CLIP_BYTES=20000000

fail() {
  echo "tada: $1" >&2
  exit 1
}

fail_unknown_sound() {
  fail "no sound named '$1' (see: tada.sh list). To use a clip of your own: tada.sh add <file> $1"
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

# --- your own clips --------------------------------------------------------

# Accepts ~/..., Windows paths (C:\Users\...) and plain paths.
normalize_path() {
  local file_path="$1"
  case "$file_path" in
    "~/"*) file_path="$HOME/${file_path#\~/}" ;;
  esac
  case "$file_path" in
    [A-Za-z]:\\* | [A-Za-z]:/*)
      if command -v cygpath >/dev/null 2>&1; then
        file_path="$(cygpath -u "$file_path")"
      fi
      ;;
  esac
  echo "$file_path"
}

# "My Bark (final).MP3" -> "my-bark-final"
name_from_file() {
  local base_name
  base_name="$(basename "$1")"
  base_name="${base_name%.*}"
  echo "$base_name" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '-' | tr -s '-' | sed 's/^-//; s/-$//' | cut -c1-40 | sed 's/-$//'
}

lowercase_extension() {
  local file_name
  file_name="$(basename "$1")"
  case "$file_name" in
    *.*) echo "${file_name##*.}" | tr '[:upper:]' '[:lower:]' ;;
    *) echo "" ;;
  esac
}

# Checks the first bytes, so a web page saved as .mp3 is caught before it fails silently at play time.
looks_like_audio() {
  local file_path="$1" extension="$2" first_bytes container_bytes
  first_bytes="$(od -An -tx1 -N4 "$file_path" | tr -d ' \n')"
  container_bytes="$(od -An -tx1 -j8 -N4 "$file_path" | tr -d ' \n')"
  case "$extension" in
    mp3) case "$first_bytes" in 494433*|fff*|ffe*) return 0 ;; esac ;;
    wav) [ "$first_bytes" = 52494646 ] && [ "$container_bytes" = 57415645 ] && return 0 ;; # RIFF....WAVE
    m4a) [ "$(od -An -tx1 -j4 -N4 "$file_path" | tr -d ' \n')" = 66747970 ] && return 0 ;; # ....ftyp
  esac
  return 1
}

file_size_bytes() {
  wc -c <"$1" | tr -d ' '
}

add_sound() {
  local source_path="$1" sound_name="$2" extension size_bytes extension_to_clear replaced=""
  [ -n "$source_path" ] || fail "usage: tada.sh add <file> [name]  (a clip you downloaded or recorded: mp3, wav or m4a)"
  source_path="$(normalize_path "$source_path")"
  [ -f "$source_path" ] || fail "no file at $source_path"

  extension="$(lowercase_extension "$source_path")"
  case " $TADA_ADDED_EXTENSIONS " in
    *" $extension "*) ;;
    *) fail "tada plays mp3, wav and m4a files, and this is '${extension:-no extension}'. Convert it first, e.g. ffmpeg -i clip.$extension clip.mp3" ;;
  esac
  looks_like_audio "$source_path" "$extension" || fail "$source_path doesn't look like a real $extension file (a download page saved by mistake?)"

  size_bytes="$(file_size_bytes "$source_path")"
  [ "$size_bytes" -le "$MAX_CLIP_BYTES" ] || fail "$source_path is $((size_bytes / 1000000)) MB; trim it to a few seconds first"

  [ -n "$sound_name" ] || sound_name="$(name_from_file "$source_path")"
  [ -n "$sound_name" ] || fail "couldn't make a name from that file name; give one: tada.sh add <file> <name>"
  is_valid_name "$sound_name" || fail "names use lowercase letters, digits and dashes, like my-bark; '$sound_name' doesn't"
  if is_known_event "$sound_name"; then
    fail "'$sound_name' is reserved for the event itself. Add the clip under another name, then: tada.sh set $sound_name <name>"
  fi
  is_bundled_sound "$sound_name" && fail "'$sound_name' is a built-in sound; pick another name: tada.sh add <file> <name>"

  mkdir -p "$TADA_USER_SOUNDS_DIR"
  for extension_to_clear in $TADA_ADDED_EXTENSIONS; do
    if [ -f "$TADA_USER_SOUNDS_DIR/$sound_name.$extension_to_clear" ]; then
      rm -f "$TADA_USER_SOUNDS_DIR/$sound_name.$extension_to_clear"
      replaced=" (replacing your earlier $sound_name)"
    fi
  done
  cp "$source_path" "$TADA_USER_SOUNDS_DIR/$sound_name.$extension"

  echo "Added $sound_name$replaced, copied to $TADA_USER_SOUNDS_DIR/$sound_name.$extension."
  if [ "$size_bytes" -gt "$LONG_CLIP_BYTES" ]; then
    echo "It's a long clip, and it plays to the end every time. A second or two works best."
  fi
  echo "Use it with: /tada:sound done $sound_name  (or needs-input)"
}

# The newest audio files in ~/Downloads, so "add the one I just downloaded" needs no path.
list_recent_downloads() {
  local downloads_dir="$HOME/Downloads" clips
  [ -d "$downloads_dir" ] || fail "no Downloads folder at $downloads_dir; give the file's path to: tada.sh add <file>"
  shopt -s nullglob nocaseglob
  clips=("$downloads_dir"/*.mp3 "$downloads_dir"/*.wav "$downloads_dir"/*.m4a)
  shopt -u nullglob nocaseglob
  if [ "${#clips[@]}" -eq 0 ]; then
    echo "No mp3, wav or m4a files in $downloads_dir."
    return
  fi
  echo "Newest audio files in $downloads_dir:"
  ls -1t "${clips[@]}" | head -n 5 | sed 's/^/  /'
  echo "Add one with: tada.sh add \"<file>\" [name]"
}

remove_sound() {
  local sound_name="$1" clip event_name
  is_valid_name "$sound_name" || fail "usage: tada.sh remove <name>  (one of your added clips; see: tada.sh list)"
  is_bundled_sound "$sound_name" && fail "'$sound_name' comes with tada and can't be removed. To stop using it: tada.sh set <event> default"
  clip="$(added_sound_file "$sound_name")"
  [ -n "$clip" ] || fail "you haven't added a sound named '$sound_name' (see: tada.sh list)"
  rm -f "$clip"
  echo "Removed $sound_name ($clip)."
  for event_name in $TADA_EVENTS; do
    if [ "$(configured_choice "$event_name")" = "$sound_name" ]; then
      echo "$event_name was set to it, so $event_name plays the default $(default_sound_name "$event_name") until you pick another."
    fi
  done
}

# Files in ~/.claude/sounds that can't be used by name, with the reason.
list_unusable_clips() {
  local extension clip sound_name
  for extension in $TADA_ADDED_EXTENSIONS; do
    for clip in "$TADA_USER_SOUNDS_DIR"/*."$extension"; do
      [ -f "$clip" ] || continue
      sound_name="$(basename "$clip" ".$extension")"
      is_known_event "$sound_name" && continue
      if ! is_valid_name "$sound_name"; then
        echo "  skipped $(basename "$clip"): rename it to lowercase letters, digits and dashes, or add it with tada.sh add"
      elif is_bundled_sound "$sound_name"; then
        echo "  skipped $(basename "$clip"): $sound_name is a built-in name, so the built-in plays; rename yours"
      fi
    done
  done
}

list_added_sounds() {
  local sound_names unusable_clips
  sound_names="$(added_sound_names)"
  unusable_clips="$(list_unusable_clips)"
  if [ -z "$sound_names" ] && [ -z "$unusable_clips" ]; then
    echo "Your sounds: none yet. Add a clip you downloaded or recorded: /tada:sound add <file>"
    echo
    return
  fi
  echo "Your sounds (in $TADA_USER_SOUNDS_DIR):"
  while IFS= read -r sound_name; do
    [ -n "$sound_name" ] || continue
    printf '  %-26s %-13s %s\n' "$sound_name" "[yours]" "$(basename "$(added_sound_file "$sound_name")")"
  done <<<"$sound_names"
  [ -n "$unusable_clips" ] && echo "$unusable_clips"
  echo
}

# --- sounds ----------------------------------------------------------------

list_sounds() {
  list_sound_group synth "Chimes and synths:"
  list_sound_group recording "Real-world sounds:"
  list_sound_group voice "Voices:"
  list_added_sounds
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
  is_library_sound "$sound_name" || fail_unknown_sound "$sound_name"
  bash "$TADA_SCRIPT_DIR/play-file.sh" "$(sound_file "$sound_name")"
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
    *) is_library_sound "$choice" || fail_unknown_sound "$choice" ;;
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
  add) add_sound "${2:-}" "${3:-}" ;;
  remove) remove_sound "${2:-}" ;;
  downloads) list_recent_downloads ;;
  *) fail "usage: tada.sh list | show | play <name> | set <done|needs-input> <name|random|off|default> | add <file> [name] | remove <name> | downloads" ;;
esac
