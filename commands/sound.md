---
description: Browse, preview and pick the tada sounds, or add your own
argument-hint: "[list | play <name> | done <name> | needs-input <name> | add <file> [name] | anything, e.g. 'something goofy for done']"
allowed-tools: Bash(bash:*)
---

Help the user pick the sounds the tada plugin plays. The tool is:

`bash "${CLAUDE_PLUGIN_ROOT}/scripts/tada.sh" <command>`

Commands: `list` (all sounds with descriptions, including ones the user added), `show` (what
plays now for each event), `play <name>` (preview), `set <done|needs-input> <name|random|off|default>`,
`add <file> [name]` (copy an mp3, wav or m4a the user has into tada under a name),
`remove <name>` (delete a clip they added), `downloads` (their newest audio files in ~/Downloads).

The user asked: $ARGUMENTS

What to do:

- Nothing asked: run `show` and `list`, print both, and say they can preview with
  `/tada:sound play <name>`, pick with `/tada:sound done <name>`, or add their own clip with
  `/tada:sound add <file>`.
- `play <name>` or just a sound name: run `play <name>`.
- `done <name>` or `needs-input <name>`: run `set`, then `play` the new sound so they hear it.
- `add <file> [name]`: run `add`, then `play` the new sound. If they also said which event it's
  for, `set` it too.
- `remove <name>`: run `remove`.
- They added or downloaded a clip but gave no path ("use the bark I just downloaded"): run
  `downloads`, pick the file that matches what they described, and `add` it. If more than one
  could match, list them and ask which.
- A description instead of a name ("something goofy", "quieter", "surprise me"): run `list`,
  choose the closest match, `set` it, `play` it, and say which one you chose and why in one line.
- They want a sound tada doesn't have, such as a character, a film or game clip, a song, or a
  specific person's voice: say in one line that tada doesn't include it, and offer the closest
  sound from `list`. Then explain how to bring their own in at most three short lines:
  1. Get the clip themselves: record it (a phone voice memo works), or download one they have
     the right to use, such as a CC0 sound from freesound.org or a free sound effect from
     pixabay.com/sound-effects.
  2. Run `/tada:sound add <file>` (or say "add the one I just downloaded").
  3. Pick it with `/tada:sound done <name>`.
     Don't search for, download, or link to copyrighted clips, and don't fetch any audio yourself.

Reply in one or two short lines, except when explaining how to bring their own sound.
Run only the tada.sh script above.
