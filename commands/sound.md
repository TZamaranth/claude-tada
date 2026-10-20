---
description: Browse, preview and pick the tada sounds
argument-hint: "[list | play <name> | done <name> | needs-input <name> | anything, e.g. 'something goofy for done']"
allowed-tools: Bash(bash:*)
---

Help the user pick the sounds the tada plugin plays. The tool is:

`bash "${CLAUDE_PLUGIN_ROOT}/scripts/tada.sh" <command>`

Commands: `list` (all sounds with descriptions), `show` (what plays now for each event),
`play <name>` (preview), `set <done|needs-input> <name|random|off|default>`.

The user asked: $ARGUMENTS

What to do:

- Nothing asked: run `show` and `list`, print both, and say they can preview with
  `/tada:sound play <name>` or pick with `/tada:sound done <name>`.
- `play <name>` or just a sound name: run `play <name>`.
- `done <name>` or `needs-input <name>`: run `set`, then `play` the new sound so they hear it.
- A description instead of a name ("something goofy", "quieter", "surprise me"): run `list`,
  choose the closest match, `set` it, `play` it, and say which one you chose and why in one line.

Reply in one or two short lines. Run only the tada.sh script above.
