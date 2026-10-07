<p align="center">
  <img src="assets/icon.svg" width="96" height="96" alt="turn-ding">
</p>

<h1 align="center">turn-ding</h1>

<p align="center"><b>English</b> · <a href="README.zh-CN.md">简体中文</a></p>

A plugin for Claude Code and Codex that rings when a turn finishes, so you can look away while it works.

You hand your coding agent a long task, switch to something else, and come back ten minutes later to find it finished nine minutes ago. turn-ding fixes that: when it is done, you hear it. If music or a video is playing, it is turned down for a moment so the ring gets through, then brought back up.

macOS only.

## What you'll hear

| What happened | Sound |
| --- | --- |
| Claude Code or Codex finished its answer | Three rings of *Glass* |
| A Claude Code turn stopped on an error | Three rings of *Basso* |
| The agent stopped to ask you something: a question with options, or permission to run a tool | One ring of *Ping* |
| You interrupted the agent | Nothing |
| A subagent finished | Nothing. Only the main turn rings |

The three sounds are different on purpose: you can tell from across the room whether to come back and read the answer, fix something, or just click a button.

Both integrations adapt to where you are: while you are actively watching the session, a turn under ten seconds ends silently and a longer one rings once without turning other audio down. When the screen is locked or you have been away for three minutes, other audio is turned down further and the sound repeats once a minute, up to five times. New input or a new turn stops the reminders.

Codex's current [lifecycle hooks](https://learn.chatgpt.com/docs/hooks) do not expose a turn-failure event, so the separate *Basso* error notification is available only in Claude Code. A failing individual tool does not count as a failed turn.

## Install

### Codex

You need macOS, Python 3.9 or later (`python3` on your PATH), and a recent Codex version with plugin and lifecycle hook support. This integration is for local CLI and desktop sessions. Every hook starts `python3`, so it should resolve to a real interpreter: a version-manager shim such as pyenv's adds over 100 ms to each one.

Install from your copy of the repository:

```bash
git clone https://github.com/1vxx/turn-ding.git ~/turn-ding
codex plugin marketplace add ~/turn-ding
codex plugin add turn-ding@turn-ding
```

Restart Codex and review and trust the turn-ding hooks. In the CLI, use `/hooks`; in the desktop app, use its hook review controls. Codex skips untrusted hooks, even when the plugin is enabled. Hooks must also be enabled (`features.hooks` must not be `false`).

After these changes are published to GitHub, you can use `codex plugin marketplace add 1vxx/turn-ding` instead of adding a local clone. To update a local installation after editing or pulling your copy, run `codex plugin add turn-ding@turn-ding` again and restart Codex. Review changed hooks again if Codex requests it.

To remove it:

```bash
codex plugin remove turn-ding@turn-ding
```

Cloud tasks cannot play sounds on your Mac through these local command hooks.

### Claude Code

You need macOS and a recent version of [Claude Code](https://claude.com/claude-code).

```bash
claude plugin marketplace add 1vxx/turn-ding
```

```bash
claude plugin install turn-ding@turn-ding
```

That's it. Start a new Claude Code session, ask anything, and you should hear three rings when the answer is done. It stays on for every session, in the terminal and in the desktop app.

To update later:

```bash
claude plugin update turn-ding@turn-ding
```

To remove it:

```bash
claude plugin uninstall turn-ding@turn-ding
```

### Just want to try it first?

Clone it and load it for a single session, with nothing installed:

```bash
git clone https://github.com/1vxx/turn-ding.git ~/turn-ding
```

```bash
claude --plugin-dir ~/turn-ding
```

### On an Intel Mac

The bundled helper is built for Apple Silicon. Without it turn-ding still rings, but it can't turn other audio down, so it plays the sound louder instead. To get the full effect, install from your own copy and build the helper there (this needs the Xcode Command Line Tools); see [Install from your own copy](#install-from-your-own-copy).

## Make it yours

There is no settings file. The values live at the top of [hooks/register.ts](hooks/register.ts) for Claude Code and [hooks/codex.py](hooks/codex.py) for Codex, so to change them you install from your own copy of the repo. Keep the values in both files in sync if you use both integrations.

### Install from your own copy

For Codex, use the [Codex installation steps](#codex) above. The steps below are for Claude Code.

```bash
git clone https://github.com/1vxx/turn-ding.git ~/turn-ding
```

```bash
sh ~/turn-ding/helper/build.sh
```

```bash
claude plugin marketplace add ~/turn-ding
```

```bash
claude plugin install turn-ding@turn-ding
```

The build step is only needed on an Intel Mac or after you change the Swift source. If you already installed from GitHub, run `claude plugin uninstall turn-ding@turn-ding` and `claude plugin marketplace remove turn-ding` first.

Installed this way, Claude Code reads the plugin straight from `~/turn-ding`. Edit a file, run `/reload-plugins` in your session, and the change is live.

### What you can change

| Value | Default | What it does |
| --- | --- | --- |
| `REPEAT` | `3` | How many times it rings when a turn ends |
| `ASK_REPEAT` | `1` | How many times it rings when the agent stops to ask |
| `RING_SECONDS` | `0.5` | How long each ring lasts, in seconds |
| `DUCK_GAIN` | `0.4` | How loud other apps stay while it rings. `0` is silent, `1` leaves them alone |
| `FALLBACK_VOLUME` | `4` | How much the sound is amplified when other audio can't be turned down. `1` is the sound's own level |
| `WATCHING_SECONDS` | `60` | Recent input window for treating the foreground session as being watched |
| `AWAY_SECONDS` | `180` | Idle time before treating you as away; locking the screen also counts |
| `QUICK_TURN_MS` | `10000` | Turns shorter than this end silently while you are watching |
| `AWAY_DUCK_GAIN` | `0.2` | How loud other apps stay while you are away |
| `REMIND_TIMES` | `5` | Maximum number of extra reminders while you are away |

The reminder interval is `REMIND_EVERY_MS = 60000` in Claude Code and `REMIND_EVERY_SECONDS = 60` in Codex.

To pick different sounds, replace `Glass` and `Ping` in your integration's file, or `Basso` in the Claude Code file, with any name from `/System/Library/Sounds`. To hear what is available:

```bash
ls /System/Library/Sounds
```

```bash
afplay /System/Library/Sounds/Hero.aiff
```

## Questions

**I don't hear anything.**
Check that your Mac isn't muted and that the right output device is selected. Then check that the plugin is installed and enabled with `claude plugin list`, and start a new session. If turn-ding can't play at all, it shows a message in Claude Code that starts with `turn-ding:` and says why.

For Codex, check `codex plugin list --marketplace turn-ding --json`, review the hooks, and confirm `python3 --version` works in Codex's environment. A short foreground turn is intentionally silent. Background playback failures are written to `notifications.log` in the plugin's `PLUGIN_DATA/codex` directory, or `$TMPDIR/turn-ding-<uid>/codex` when plugin data is unavailable.

**It rings, but my music doesn't get quieter.**
The helper that turns other audio down didn't run, so turn-ding fell back to plain playback. This is expected on an Intel Mac; see [Install from your own copy](#install-from-your-own-copy) to build it.

**It's too loud / too quiet.**
The ring follows your system volume. To change how much other apps are turned down, adjust `DUCK_GAIN`.

**Does it ring for every subagent?**
Not when they finish. Only the main conversation rings at the end of a turn, so a task that fans out into ten subagents rings once, at the end. A subagent that stops to ask you something does ring, because it is waiting on you.

**Will my music stay quiet if something goes wrong?**
No. The helper restores the volume when it finishes, and also if it is killed partway through.

**Does it work on Linux or Windows?**
Not today. It relies on macOS system sounds and macOS audio APIs.

## How it works

turn-ding listens for Claude Code's `turn.complete` event. When the main turn ends, it runs a small Swift helper ([helper/turn-ding.swift](helper/turn-ding.swift)) that asks the macOS audio mixer to turn every other app down, plays the sound, and turns them back up. Other apps' audio is only scaled, never paused, so the dip is smooth.

Codex loads a separate native manifest and [command hook configuration](hooks/codex.json). `Stop` rings for the main turn, `PreToolUse` rings for question tools, and `PermissionRequest` rings for approvals. `UserPromptSubmit`, `PostToolUse`, `Interrupt`, and `SessionEnd` cancel reminders when work resumes or ends. The Python adapter launches a bounded playback worker using the same Swift helper; hooks return JSON without changing tool permissions. Session timing and cancellation tokens live outside the repository; no prompts or transcripts are stored.

The mixer call it uses, `AudioDeviceDuck`, is exported by CoreAudio but is not in a public header, so a future macOS release could change it. If it ever fails, turn-ding falls back to `afplay` and plays the sound louder instead. You still get your ring.

## Development

```
.claude-plugin/plugin.json   plugin manifest
.claude-plugin/marketplace.json   lets `claude plugin install` find it
.codex-plugin/plugin.json    Codex manifest; selects separate command hooks
hooks/hooks.json             names the hooks module
hooks/register.ts            the plugin
hooks/register.test.ts       tests
hooks/codex.json             Codex lifecycle hooks
hooks/codex.py               Codex adapter and playback worker
hooks/codex_test.py          Codex tests (Python standard library)
helper/turn-ding.swift       source of the audio helper
helper/build.sh              builds bin/turn-ding
bin/turn-ding                the built helper (arm64)
```

Check the plugin and run the tests:

```bash
claude plugin validate .
```

```bash
claude plugin test .
```

Test the Codex adapter without playing audio:

```bash
python3 -m unittest discover -s hooks -p codex_test.py -v
```

Rebuild the helper after changing the Swift source:

```bash
sh helper/build.sh
```

Issues and pull requests are welcome.

## License

[MIT](LICENSE)
