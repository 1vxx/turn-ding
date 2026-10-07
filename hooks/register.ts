import type { EngineInterface, Register } from 'claude-code'

const SOUNDS = '/System/Library/Sounds'
// How many times the sound rings when a turn ends and when Claude stops to
// ask, and how long each ring lasts
const REPEAT = 3
const ASK_REPEAT = 1
const RING_SECONDS = '0.5'
// What the other apps' audio is turned down to while it rings: 0 silent, 1 untouched
const DUCK_GAIN = '0.4'
// afplay's gain for the fallback: 1 is the file's own level, above it is amplified
const FALLBACK_VOLUME = '4'

// Rings through bin/turn-ding, which has the system turn the other apps down
// meanwhile
const ringDucked = async ($: EngineInterface, file: string, repeat: number) => {
  const { exitCode, stderr } = await $.process.run([`${$.plugin.root}/bin/turn-ding`, file, String(repeat), RING_SECONDS, DUCK_GAIN])
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
const ring = async ($: EngineInterface, sound: string, repeat: number) => {
  const file = `${SOUNDS}/${sound}.aiff`
  try {
    await ringDucked($, file, repeat).catch(() => ringPlain($, file, repeat))
  } catch (err) {
    $.ui.toast(`turn-ding: ${err instanceof Error ? err.message : String(err)}`)
  }
}

export const register: Register = (on) => {
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    // Subagent turns and turns the user interrupted stay silent
    if (e.agentId === undefined && e.reason !== 'aborted') {
      await ring($, e.reason === 'answer' ? 'Glass' : 'Basso', REPEAT)
    }
    return result
  })

  // Claude stopping to ask rings once, a subagent's asking included. The ring
  // is not awaited, so the dialog opens at once, and a failure here never
  // stands in the way of the call
  on('tool.call', { tool: 'AskUserQuestion' }, ($, e, next) => {
    void ring($, 'Ping', ASK_REPEAT)
    return next(e)
  }).catch((_$, e, next) => next(e))
  on('classic.PermissionRequest', ($, e, next) => {
    // A question has rung already
    if (e.tool_name !== 'AskUserQuestion') void ring($, 'Ping', ASK_REPEAT)
    return next(e)
  }).catch((_$, e, next) => next(e))
}
