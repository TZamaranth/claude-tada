# tada for Claude Code

A Claude Code plugin that plays a sound when Claude is done, so you can look away
while it works.

- **Ta-da!** when Claude finishes a turn
- **Hm?** (a soft rising chime) when Claude is waiting on your permission

Works on macOS, Windows and Linux. Swap in any sound file you like.

## Install

### Option 1: from GitHub (recommended)

In Claude Code, run:

```
/plugin marketplace add pjbiz/claude-tada
/plugin install tada@tada
```

Then run `/reload-plugins` (or restart Claude Code). Finish any prompt and you should hear it.

From a terminal instead:

```bash
claude plugin marketplace add pjbiz/claude-tada
claude plugin install tada@tada
```

### Option 2: download the package

1. Download `tada-v1.0.0.zip` from the [latest release](https://github.com/pjbiz/claude-tada/releases/latest).
2. Unzip it somewhere permanent, for example your home folder. You get a `tada` folder.
3. In Claude Code, add that folder and install:

   ```
   /plugin marketplace add ~/tada
   /plugin install tada@tada
   ```

   On Windows, use the full path: `/plugin marketplace add C:\Users\you\tada`.

To try it for one session without installing anything, run `claude --plugin-dir path/to/tada-v1.0.0.zip`.

## Use your own sounds

Put a file in `~/.claude/sounds/` named after the event:

| Event                      | File name                        |
| -------------------------- | -------------------------------- |
| Claude finished            | `done.mp3` (or `.wav`, `.m4a`)   |
| Claude needs your approval | `needs-input.mp3` (same formats) |

Your file wins over the bundled one, and plugin updates leave it alone. Delete it
to go back to the default. Keep it short (1 to 2 seconds) and use audio you have
the rights to.

On Windows, `~/.claude/sounds/` is `C:\Users\<you>\.claude\sounds\`.

## Requirements

| OS      | Needs                                                                                                |
| ------- | ---------------------------------------------------------------------------------------------------- |
| macOS   | Nothing extra (`afplay` is built in)                                                                 |
| Windows | [Git for Windows](https://git-scm.com/downloads/win) (Git Bash), which Claude Code recommends anyway |
| Linux   | One of `paplay`, `pw-play`, `aplay` or `ffplay`. Without a player you get a terminal bell.           |

On Windows without Git Bash, Claude Code runs hooks through PowerShell and this
plugin stays silent. It never blocks or breaks your session.

## Update or remove

```bash
claude plugin update tada@tada
claude plugin uninstall tada@tada
```

Or use `/plugin` in Claude Code and pick the plugin under **Installed**.

## How it works

`hooks/hooks.json` registers two hooks:

- `Stop` runs `scripts/play-sound.sh done`
- `Notification` (matcher `permission_prompt`) runs `scripts/play-sound.sh needs-input`

Both run in the background (`async`), so Claude never waits on the sound.
`play-sound.sh` looks for your own file first, then the bundled one, and picks the
player for your OS. On Windows it hands off to `scripts/play-sound.ps1`, which uses
the built-in Windows media player so `.mp3` and `.m4a` work too.

## The sounds

The bundled sounds are not recordings. `tools/make-sounds.py` synthesizes them
from sine waves using only the Python standard library. To tweak the notes and
rebuild them:

```bash
python tools/make-sounds.py
```

They are released under CC0 (public domain). See [sounds/CREDITS.md](sounds/CREDITS.md).

## License

Code: [MIT](LICENSE). Sounds: CC0.
