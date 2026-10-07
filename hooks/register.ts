import type { EngineInterface, Register } from 'claude-code'

const SOUNDS = '/System/Library/Sounds'
// How many times the sound rings, and how long each ring lasts
const REPEAT = 3
const RING_SECONDS = '0.5'
// What the other apps' audio is turned down to while it rings: 0 silent, 1 untouched
const DUCK_GAIN = '0.4'
// afplay's gain for the fallback: 1 is the file's own level, above it is amplified
const FALLBACK_VOLUME = '4'

// Rings through bin/turn-ding, which has the system turn the other apps down
// meanwhile
const ringDucked = async ($: EngineInterface, file: string) => {
  const { exitCode, stderr } = await $.process.run([`${$.plugin.root}/bin/turn-ding`, file, String(REPEAT), RING_SECONDS, DUCK_GAIN])
  if (exitCode !== 0) throw new Error(stderr.trim() || `turn-ding exited ${exitCode}`)
}

// Rings through afplay alone, louder, with nothing turned down
const ringPlain = async ($: EngineInterface, file: string) => {
  for (let i = 0; i < REPEAT; i++) {
    const { exitCode, stderr } = await $.process.run(['/usr/bin/afplay', '-v', FALLBACK_VOLUME, '-t', RING_SECONDS, file])
    if (exitCode !== 0) throw new Error(`afplay exited ${exitCode}: ${stderr.trim()}`)
  }
}

export const register: Register = (on) => {
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    // Subagent turns and turns the user interrupted stay silent
    if (e.agentId === undefined && e.reason !== 'aborted') {
      const file = `${SOUNDS}/${e.reason === 'answer' ? 'Glass' : 'Basso'}.aiff`
      try {
        await ringDucked($, file).catch(() => ringPlain($, file))
      } catch (err) {
        $.ui.toast(`turn-ding: ${err instanceof Error ? err.message : String(err)}`)
      }
    }
    return result
  })
}
