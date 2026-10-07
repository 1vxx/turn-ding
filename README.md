# turn-ding 🔔

**English** · [简体中文](README.zh-CN.md)

A Claude Code plugin that rings when Claude finishes a turn, so you can look away while it works.

You hand Claude a long task, switch to something else, and come back ten minutes later to find it finished nine minutes ago. turn-ding fixes that: when Claude is done, you hear it. If music or a video is playing, it is turned down for a moment so the ring gets through, then brought back up.

macOS only.

## What you'll hear

| What happened | Sound |
| --- | --- |
| Claude finished its answer | Three rings of *Glass* |
| The turn stopped on an error | Three rings of *Basso* |
| You interrupted Claude | Nothing |
| A subagent finished | Nothing. Only the main turn rings |

The two sounds are different on purpose: you can tell from across the room whether to come back and read the answer or come back and fix something.

## Install

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

There is no settings file. The values live at the top of [hooks/register.ts](hooks/register.ts), so to change them you install from your own copy of the repo.

### Install from your own copy

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
| `REPEAT` | `3` | How many times it rings |
| `RING_SECONDS` | `0.5` | How long each ring lasts, in seconds |
| `DUCK_GAIN` | `0.4` | How loud other apps stay while it rings. `0` is silent, `1` leaves them alone |
| `FALLBACK_VOLUME` | `4` | How much the sound is amplified when other audio can't be turned down. `1` is the sound's own level |

To pick different sounds, replace `Glass` and `Basso` in the same file with any name from `/System/Library/Sounds`. To hear what is available:

```bash
ls /System/Library/Sounds
```

```bash
afplay /System/Library/Sounds/Hero.aiff
```

## Questions

**I don't hear anything.**
Check that your Mac isn't muted and that the right output device is selected. Then check that the plugin is installed and enabled with `claude plugin list`, and start a new session. If turn-ding can't play at all, it shows a message in Claude Code that starts with `turn-ding:` and says why.

**It rings, but my music doesn't get quieter.**
The helper that turns other audio down didn't run, so turn-ding fell back to plain playback. This is expected on an Intel Mac; see [Install from your own copy](#install-from-your-own-copy) to build it.

**It's too loud / too quiet.**
The ring follows your system volume. To change how much other apps are turned down, adjust `DUCK_GAIN`.

**Does it ring for every subagent?**
No. Only the main conversation rings, so a task that fans out into ten subagents rings once, at the end.

**Will my music stay quiet if something goes wrong?**
No. The helper restores the volume when it finishes, and also if it is killed partway through.

**Does it work on Linux or Windows?**
Not today. It relies on macOS system sounds and macOS audio APIs.

## How it works

turn-ding listens for Claude Code's `turn.complete` event. When the main turn ends, it runs a small Swift helper ([helper/turn-ding.swift](helper/turn-ding.swift)) that asks the macOS audio mixer to turn every other app down, plays the sound, and turns them back up. Other apps' audio is only scaled, never paused, so the dip is smooth.

The mixer call it uses, `AudioDeviceDuck`, is exported by CoreAudio but is not in a public header, so a future macOS release could change it. If it ever fails, turn-ding falls back to `afplay` and plays the sound louder instead. You still get your ring.

## Development

```
.claude-plugin/plugin.json   plugin manifest
.claude-plugin/marketplace.json   lets `claude plugin install` find it
hooks/hooks.json             names the hooks module
hooks/register.ts            the plugin
hooks/register.test.ts       tests
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

Rebuild the helper after changing the Swift source:

```bash
sh helper/build.sh
```

Issues and pull requests are welcome.
