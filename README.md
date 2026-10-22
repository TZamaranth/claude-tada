# tada for Claude Code

A Claude Code plugin that plays a sound when Claude is done, so you can look away
while it works.

- **Ta-da!** when Claude finishes a turn
- **Hm?** (a soft rising chime) when Claude is waiting on your permission

65 sounds to choose from: chimes and chiptunes, real-world sounds (ka-ching, a
toilet flush, a cow, an air horn) and announcer voices ("Mission completed.").
Works on macOS, Windows and Linux, and you can bring your own sound files too.

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

1. Download the `tada-v*.zip` file from the [latest release](https://github.com/pjbiz/claude-tada/releases/latest).
2. Unzip it somewhere permanent, for example your home folder. You get a `tada` folder.
3. In Claude Code, add that folder and install:

   ```
   /plugin marketplace add ~/tada
   /plugin install tada@tada
   ```

   On Windows, use the full path: `/plugin marketplace add C:\Users\you\tada`.

To try it for one session without installing anything, run `claude --plugin-dir path/to/tada-v1.2.0.zip`.

## Pick your sounds

Listen to all of them on the [preview page](https://pjbiz.github.io/claude-tada/docs/),
or in Claude Code:

```
/tada:sound                        what plays now, and every sound
/tada:sound play kazoo             preview one
/tada:sound done coin              play "coin" when Claude finishes
/tada:sound needs-input knock      play "knock" when Claude needs permission
/tada:sound done random            a different sound every time
/tada:sound needs-input off        silence one event
/tada:sound something goofy for done
```

The last one works because Claude reads the list and picks for you.

**Chimes and synths:** tada (default for done), coin, level-up, power-up, fanfare,
marimba, kalimba, harp, ding, doorbell, wind-chimes, sparkle, success, champagne,
drumroll, cuckoo, bird, boing, slide-whistle, kazoo, bubbles, robot, hm (default for
needs-input), knock, sonar, blip, huh, glass-tap, triple-beep, tick-tock, owl

**Real-world sounds:** ka-ching, toilet-flush, crowd-cheer, party-horn, microwave,
jackpot, gong, rubber-duck, cow, duck-quack, typewriter-ding, burp, fart, air-horn,
woohoo, magic-wand, evil-laugh, boxing-bell, sad-trombone, rooster, cat-meow,
dog-bark, ahem, referee-whistle, phone-ring, bicycle-bell

**Voices:** voice-congratulations, voice-mission-complete, voice-objective-achieved,
voice-you-win, voice-new-highscore, voice-level-up, voice-hurry-up, voice-ready

Any sound works for either event. Your choices are saved in `~/.claude/tada.conf`,
which you can also edit by hand:

```
done=kazoo
needs-input=owl
```

Without Claude, the same tool runs from a terminal:
`bash <plugin folder>/scripts/tada.sh list | show | play <name> | set <event> <name>`.

## Use your own sound files

Put a file in `~/.claude/sounds/` named after the event:

| Event                      | File name                        |
| -------------------------- | -------------------------------- |
| Claude finished            | `done.mp3` (or `.wav`, `.m4a`)   |
| Claude needs your approval | `needs-input.mp3` (same formats) |

Your file wins over any choice in `tada.conf`, and plugin updates leave it alone.
Delete it to go back. Keep it short (1 to 2 seconds) and use audio you have the
rights to.

On Windows, `~/.claude/` is `C:\Users\<you>\.claude\`.

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
Uninstalling leaves `~/.claude/tada.conf` and `~/.claude/sounds/` in place; delete
them by hand if you want them gone.

## How it works

`hooks/hooks.json` registers two hooks:

- `Stop` runs `scripts/play-sound.sh done`
- `Notification` (matcher `permission_prompt`) runs `scripts/play-sound.sh needs-input`

Both run in the background (`async`), so Claude never waits on the sound.
`play-sound.sh` picks the file in this order: your own file in `~/.claude/sounds/`,
then your choice in `~/.claude/tada.conf`, then the default. `play-file.sh` plays it
with your OS's player. On Windows it hands off to `scripts/play-sound.ps1`, which
uses the built-in Windows media player so `.mp3` and `.m4a` work too.

## The sounds

Every bundled sound is public domain (CC0), so you can use them anywhere.

- **Chimes and synths** are generated by `tools/make-sounds.py` from oscillators,
  filtered noise and a plucked-string model, using only the Python standard library.
- **Real-world sounds** are recordings their authors released as CC0 on
  [Freesound](https://freesound.org).
- **Voices** come from Kenney's CC0 [Voiceover Pack](https://kenney.nl/assets/voiceover-pack).

[sounds/CREDITS.md](sounds/CREDITS.md) links every recording to its source and author.
`sounds/recordings.json` records exactly where each one came from and how it was
trimmed, so the files can be rebuilt and checked:

```bash
pip install -r tools/requirements.txt
python tools/import-recordings.py   # downloads the CC0 sources, writes the recorded .wav files
python tools/make-sounds.py         # synthesizes the rest, writes catalog.tsv and CREDITS.md
python tools/make-preview.py        # rebuilds the preview page
```

To add a recording, add an entry to `sounds/recordings.json`. Only CC0 sources are
accepted; the importer refuses anything else.

## License

Code: [MIT](LICENSE). Sounds: CC0.
