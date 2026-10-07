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

**1. Get the plugin**

```bash
git clone https://github.com/1vxx/turnding.git ~/turnding
```

**2. Try it for one session**

```bash
claude --plugin-dir ~/turnding
```

Ask Claude anything. When it finishes answering, you should hear three rings.

**3. Keep it on for every session**

Add the folder to the `env` block of `~/.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_PLUGIN_DIRS": "~/turnding"
  }
}
```

This also covers sessions started from the Claude desktop app, where there is no command line to add a flag to.

### On an Intel Mac

The bundled helper is built for Apple Silicon. On an Intel Mac, rebuild it once (this needs the Xcode Command Line Tools):

```bash
sh ~/turnding/helper/build.sh
```

If you skip this, turn-ding still rings. It just can't turn other audio down, so it plays the sound louder instead.

## Make it yours

There is no settings file. Open [hooks/register.ts](hooks/register.ts) and change the values at the top:

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
Check that your Mac isn't muted and that the right output device is selected. Then check that the plugin is loaded: start Claude with `claude --plugin-dir ~/turnding` and ask it something short. If turn-ding can't play at all, it shows a message in Claude Code that starts with `turn-ding:` and says why.

**It rings, but my music doesn't get quieter.**
The helper that turns other audio down didn't run, so turn-ding fell back to plain playback. Rebuild it with `sh ~/turnding/helper/build.sh`.

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
