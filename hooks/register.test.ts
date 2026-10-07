import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const turn = { answer: 'done', durationMs: 1, isAborted: false, turnId: 't1' }
const GLASS = '/System/Library/Sounds/Glass.aiff'
const BASSO = '/System/Library/Sounds/Basso.aiff'
const PING = '/System/Library/Sounds/Ping.aiff'

// Stands for the engine: records each run as "<program> <sound>" and ends the turn
const record = (on: On, duckExitCode = 0) => {
  const runs: string[] = []
  on('process.run', async (_$, e) => {
    const program = e.argv[0]?.split('/').at(-1) ?? ''
    runs.push(`${program} ${e.argv.find((arg) => arg.endsWith('.aiff'))}`)
    const exitCode = program === 'turn-ding' ? duckExitCode : 0
    return { value: { exitCode, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('turn.complete', async (_$, e) => ({ text: e.answer }))
  on('tool.call', async () => ({ result: {} }))
  on('classic.PermissionRequest', async () => ({}))
  return runs
}

test('rings through the ducking helper when the main turn answers', async ($, on) => {
  const runs = record(on)
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([`turn-ding ${GLASS}`])
})

test('uses the error sound when the turn dies on an error', async ($, on) => {
  const runs = record(on)
  await $.turn.complete({ ...turn, reason: 'error' })
  expect(runs).toEqual([`turn-ding ${BASSO}`])
})

test('falls back to three afplay rings when the helper fails', async ($, on) => {
  const runs = record(on, 1)
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([`turn-ding ${GLASS}`, ...Array(3).fill(`afplay ${GLASS}`)])
})

test('stays silent for subagents and interrupted turns', async ($, on) => {
  const runs = record(on)
  await $.turn.complete({ ...turn, reason: 'answer', agentId: 'a1' })
  await $.turn.complete({ ...turn, reason: 'aborted', isAborted: true })
  expect(runs).toEqual([])
})

test('rings once when Claude asks a question', async ($, on) => {
  const runs = record(on)
  const clock = mock.clock(on)
  await $.tool.call({ tool: 'AskUserQuestion', questions: [] })
  await clock.settle()
  expect(runs).toEqual([`turn-ding ${PING}`])
})

test('rings once when a tool call needs permission', async ($, on) => {
  const runs = record(on)
  const clock = mock.clock(on)
  await $.classic.PermissionRequest({ tool_name: 'Bash', tool_input: { command: 'ls' } })
  await clock.settle()
  expect(runs).toEqual([`turn-ding ${PING}`])
})

test('does not ring twice when a question also asks permission', async ($, on) => {
  const runs = record(on)
  const clock = mock.clock(on)
  await $.classic.PermissionRequest({ tool_name: 'AskUserQuestion', tool_input: { questions: [] } })
  await clock.settle()
  expect(runs).toEqual([])
})
