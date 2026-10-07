import type { EngineInterface, Register } from 'claude-code'

const SOUNDS = '/System/Library/Sounds'
// How many times the sound rings when a turn ends and when Claude stops to
// ask, and how long each ring lasts
const REPEAT = 3
const ASK_REPEAT = 1
const RING_SECONDS = '0.5'
// What the other apps' audio is turned down to while it rings: 0 silent, 1 untouched
const DUCK_GAIN = '0.4'
// The person is watching while the session's app is in front and they touched
// the keyboard or pointer this recently, and away once they have not for this
// long or the screen is locked
const WATCHING_SECONDS = 60
const AWAY_SECONDS = 180
// A turn this short ends silently while they watch
const QUICK_TURN_MS = 10_000
// While they are away: what the other apps are turned down to, and how often
// and how many times the ring comes again until they are back
const AWAY_DUCK_GAIN = '0.2'
const REMIND_EVERY_MS = 60_000
const REMIND_TIMES = 5
// afplay's gain for the fallback: 1 is the file's own level, above it is amplified
const FALLBACK_VOLUME = '4'

// Rings through bin/turn-ding, which has the system turn the other apps down
// meanwhile
const ringDucked = async ($: EngineInterface, file: string, repeat: number, gain: string) => {
  const { exitCode, stderr } = await $.process.run([`${$.plugin.root}/bin/turn-ding`, file, String(repeat), RING_SECONDS, gain])
  if (exitCode !== 0) throw new Error(stderr.trim() || `turn-ding exited ${exitCode}`)
}

// Rings through afplay alone, louder, with nothing turned down
const ringPlain = async ($: EngineInterface, file: string, repeat: number) => {
  for (let i = 0; i < repeat; i++) {
    const { exitCode, stderr } = await $.process.run(['/usr/bin/afplay', '-v', FALLBACK_VOLUME, '-t', RING_SECONDS, file])
    if (exitCode !== 0) throw new Error(`afplay exited ${exitCode}: ${stderr.trim()}`)
  }
}

// Rings ducked, plainly when that fails, and says so when neither works
const ring = async ($: EngineInterface, sound: string, repeat: number, gain = DUCK_GAIN) => {
  const file = `${SOUNDS}/${sound}.aiff`
  try {
    await ringDucked($, file, repeat, gain).catch(() => ringPlain($, file, repeat))
  } catch (err) {
    $.ui.toast(`turn-ding: ${err instanceof Error ? err.message : String(err)}`)
  }
}

// Where the person is, as bin/turn-ding reads it from the system; when it
// cannot say, they are taken to be at the machine doing something else
const where = async ($: EngineInterface) => {
  try {
    const { exitCode, stdout } = await $.process.run([`${$.plugin.root}/bin/turn-ding`, 'state'])
    const [idle, locked, front] = stdout.trim().split(' ').map(Number)
    if (exitCode !== 0 || idle === undefined || Number.isNaN(idle)) return { idleSeconds: 0, presence: 'elsewhere' as const }
    const presence = locked === 1 || idle >= AWAY_SECONDS ? 'away' : front === 1 && idle < WATCHING_SECONDS ? 'watching' : 'elsewhere'
    return { idleSeconds: idle, presence } as const
  } catch {
    return { idleSeconds: 0, presence: 'elsewhere' as const }
  }
}

let reminder: { cancel: () => void } | undefined
const stopReminding = () => {
  reminder?.cancel()
  reminder = undefined
}

// Rings as loudly as where the person is calls for: once and with nothing
// turned down while they watch (not at all after a quick turn), in full when
// they are doing something else, and again and again while they are away
const notify = async ($: EngineInterface, sound: string, repeat: number, turnMs = Infinity) => {
  stopReminding()
  const { presence } = await where($)
  if (presence === 'watching') {
    if (turnMs >= QUICK_TURN_MS) await ring($, sound, 1, '1')
    return
  }
  if (presence === 'elsewhere') return ring($, sound, repeat)
  let left = REMIND_TIMES
  reminder = $.clock.every(REMIND_EVERY_MS, () => {
    void (async () => {
      // Any input since the last ring means they are back
      if (left-- === 0 || (await where($)).idleSeconds * 1000 < REMIND_EVERY_MS) return stopReminding()
      await ring($, sound, 1, AWAY_DUCK_GAIN)
    })()
  })
  await ring($, sound, repeat, AWAY_DUCK_GAIN)
}

export const register: Register = (on) => {
  on('turn.start', ($, e, next) => {
    stopReminding()
    return next(e)
  })
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    // Subagent turns and turns the user interrupted stay silent
    if (e.agentId === undefined && e.reason !== 'aborted') {
      await notify($, e.reason === 'answer' ? 'Glass' : 'Basso', REPEAT, e.durationMs)
    }
    return result
  })

  // Claude stopping to ask rings once, a subagent's asking included. The ring
  // is not awaited, so the dialog opens at once, and a failure here never
  // stands in the way of the call
  on('tool.call', { tool: 'AskUserQuestion' }, ($, e, next) => {
    void notify($, 'Ping', ASK_REPEAT)
    return next(e)
  }).catch((_$, e, next) => next(e))
  on('classic.PermissionRequest', ($, e, next) => {
    // A question has rung already
    if (e.tool_name !== 'AskUserQuestion') void notify($, 'Ping', ASK_REPEAT)
    return next(e)
  }).catch((_$, e, next) => next(e))
}
