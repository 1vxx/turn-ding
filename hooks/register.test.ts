import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const turn = { answer: 'done', durationMs: 1, isAborted: false, turnId: 't1' }
const GLASS = '/System/Library/Sounds/Glass.aiff'
const BASSO = '/System/Library/Sounds/Basso.aiff'
const PING = '/System/Library/Sounds/Ping.aiff'

type State = string | { exitCode: number; stdout: string } | Error

const helperCall = (sound: string, repeat: number, gain: string) => [
  expect.stringMatching(/\/bin\/turn-ding$/), sound, String(repeat), '0.5', gain,
]

// Stands for the engine: records complete audio and state-query argv without
// running any process. The mutable state is the helper's idle/locked/front reply.
const record = (on: On, duckExitCode = 0, state: State = '5 0 0') => {
  const fixture = { runs: [] as string[][], stateQueries: [] as string[][], state, clock: mock.clock(on) }
  on('process.run', async (_$, e) => {
    const argv = [...e.argv]
    const program = argv[0]?.split('/').at(-1) ?? ''
    if (argv[1] === 'state') {
      fixture.stateQueries.push(argv)
      if (fixture.state instanceof Error) throw fixture.state
      const { exitCode, stdout } = typeof fixture.state === 'string'
        ? { exitCode: 0, stdout: fixture.state }
        : fixture.state
      return { value: { exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    }
    fixture.runs.push(argv)
    const exitCode = program === 'turn-ding' ? duckExitCode : 0
    return { value: { exitCode, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('turn.complete', async (_$, e) => ({ text: e.answer }))
  on('turn.start', async (_$, e) => ({ turnId: e.turnId }))
  on('tool.call', async () => ({ result: {} }))
  on('classic.PermissionRequest', async () => ({}))
  return fixture
}

test('rings through the ducking helper when the main turn answers', async ($, on) => {
  const { runs, clock } = record(on)
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([helperCall(GLASS, 3, '0.4')])
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(GLASS, 3, '0.4')])
})

test('uses the error sound when the turn dies on an error', async ($, on) => {
  const { runs } = record(on)
  await $.turn.complete({ ...turn, reason: 'error' })
  expect(runs).toEqual([helperCall(BASSO, 3, '0.4')])
})

test('falls back to three afplay rings when the helper fails', async ($, on) => {
  const { runs } = record(on, 1)
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([
    helperCall(GLASS, 3, '0.4'),
    ...Array(3).fill(['/usr/bin/afplay', '-v', '4', '-t', '0.5', GLASS]),
  ])
})

test('stays silent for subagents and interrupted turns', async ($, on) => {
  const { runs } = record(on)
  await $.turn.complete({ ...turn, reason: 'answer', agentId: 'a1' })
  await $.turn.complete({ ...turn, reason: 'aborted', isAborted: true })
  expect(runs).toEqual([])
})

test('rings once when Claude asks a question', async ($, on) => {
  const { runs, clock } = record(on, 0, '5 0 1')
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([])
  await $.tool.call({ tool: 'AskUserQuestion', questions: [] })
  await clock.settle()
  expect(runs).toEqual([helperCall(PING, 1, '1')])
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(PING, 1, '1')])
})

test('rings once when a tool call needs permission', async ($, on) => {
  const { runs, clock } = record(on, 0, '5 0 1')
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([])
  await $.classic.PermissionRequest({ tool_name: 'Bash', tool_input: { command: 'ls' } })
  await clock.settle()
  expect(runs).toEqual([helperCall(PING, 1, '1')])
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(PING, 1, '1')])
})

test('does not ring twice when a question also asks permission', async ($, on) => {
  const { runs, clock } = record(on)
  await $.classic.PermissionRequest({ tool_name: 'AskUserQuestion', tool_input: { questions: [] } })
  await clock.settle()
  expect(runs).toEqual([])
  await $.tool.call({ tool: 'AskUserQuestion', questions: [] })
  await clock.settle()
  expect(runs).toEqual([helperCall(PING, 1, '0.4')])
})

test('rings once while the person watches, and not at all after a quick turn', async ($, on) => {
  const { runs, clock } = record(on, 0, '5 0 1')
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([])
  await $.turn.complete({ ...turn, durationMs: 60_000, reason: 'answer' })
  expect(runs).toEqual([helperCall(GLASS, 1, '1')])
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(GLASS, 1, '1')])
})

test('rings again while the person is away, until they are back', async ($, on) => {
  const { runs, clock } = record(on, 0, '600 0 0')
  await $.turn.complete({ ...turn, reason: 'answer' })
  await clock.advance(59_999)
  expect(runs).toEqual([helperCall(GLASS, 3, '0.2')])
  await clock.advance(1)
  expect(runs).toEqual([helperCall(GLASS, 3, '0.2'), helperCall(GLASS, 1, '0.2')])
  await $.turn.start({ text: 'next', turnId: 't2' })
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(GLASS, 3, '0.2'), helperCall(GLASS, 1, '0.2')])
})

test('uses the 10-second quick-turn boundary while foreground idle is below 60 seconds', async ($, on) => {
  const { runs, clock } = record(on, 0, '59 0 1')
  await $.turn.complete({ ...turn, durationMs: 9_999, reason: 'answer' })
  expect(runs).toEqual([])
  await $.turn.complete({ ...turn, durationMs: 10_000, reason: 'answer' })
  expect(runs).toEqual([helperCall(GLASS, 1, '1')])
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(GLASS, 1, '1')])
})

test('uses the normal notification at exactly 60 seconds of foreground idle', async ($, on) => {
  const { runs, clock } = record(on, 0, '60 0 1')
  await $.turn.complete({ ...turn, durationMs: 9_999, reason: 'answer' })
  expect(runs).toEqual([helperCall(GLASS, 3, '0.4')])
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(GLASS, 3, '0.4')])
})

test('uses the normal notification just before 180 seconds of idle', async ($, on) => {
  const { runs, clock } = record(on, 0, '179 0 1')
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([helperCall(GLASS, 3, '0.4')])
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(GLASS, 3, '0.4')])
})

test('a locked screen takes priority over recent foreground input', async ($, on) => {
  const fixture = record(on, 0, '5 1 1')
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(fixture.runs).toEqual([helperCall(GLASS, 3, '0.2')])
  // Idle grows while the locked screen receives no new input.
  fixture.state = '65 1 1'
  await fixture.clock.advance(60_000)
  expect(fixture.runs).toEqual([helperCall(GLASS, 3, '0.2'), helperCall(GLASS, 1, '0.2')])
})

for (const [label, state] of [
  ['idle is exactly 180 seconds', '180 0 0'],
  ['the screen is locked despite idle below 180 seconds', '60 1 1'],
]) {
  test(`uses away gain and one-minute reminders when ${label}`, async ($, on) => {
    const { runs, clock } = record(on, 0, state)
    await $.turn.complete({ ...turn, reason: 'answer' })
    expect(runs).toEqual([helperCall(GLASS, 3, '0.2')])
    await clock.advance(59_999)
    expect(runs).toEqual([helperCall(GLASS, 3, '0.2')])
    await clock.advance(1)
    expect(runs).toEqual([helperCall(GLASS, 3, '0.2'), helperCall(GLASS, 1, '0.2')])
    await clock.advance(60_000)
    expect(runs).toEqual([
      helperCall(GLASS, 3, '0.2'),
      helperCall(GLASS, 1, '0.2'),
      helperCall(GLASS, 1, '0.2'),
    ])
  })
}

test('stops reminders after recent input in another app and does not restart them', async ($, on) => {
  const fixture = record(on, 0, '600 0 0')
  await $.turn.complete({ ...turn, reason: 'answer' })
  fixture.state = '60 0 0'
  await fixture.clock.advance(60_000)
  const expected = [helperCall(GLASS, 3, '0.2'), helperCall(GLASS, 1, '0.2')]
  expect(fixture.runs).toEqual(expected)
  fixture.state = '59 0 0'
  await fixture.clock.advance(60_000)
  expect(fixture.runs).toEqual(expected)
  fixture.state = '600 0 0'
  await fixture.clock.advance(600_000)
  expect(fixture.runs).toEqual(expected)
  expect(fixture.stateQueries.length).toBe(3)
})

test('adds at most five reminders while away, then stays silent', async ($, on) => {
  const { runs, clock } = record(on, 0, '600 0 0')
  await $.turn.complete({ ...turn, reason: 'answer' })
  expect(runs).toEqual([helperCall(GLASS, 3, '0.2')])
  for (let count = 1; count <= 5; count++) {
    await clock.advance(60_000)
    expect(runs).toEqual([helperCall(GLASS, 3, '0.2'), ...Array(count).fill(helperCall(GLASS, 1, '0.2'))])
  }
  await clock.advance(60_000)
  await clock.advance(600_000)
  expect(runs).toEqual([helperCall(GLASS, 3, '0.2'), ...Array(5).fill(helperCall(GLASS, 1, '0.2'))])
})

test('replaces the old reminder schedule and sound when a new notification arrives', async ($, on) => {
  const { runs, clock } = record(on, 0, '600 0 0')
  await $.turn.complete({ ...turn, reason: 'answer' })
  await clock.advance(30_000)
  await $.turn.complete({ ...turn, reason: 'error', turnId: 't2' })
  const initial = [helperCall(GLASS, 3, '0.2'), helperCall(BASSO, 3, '0.2')]
  expect(runs).toEqual(initial)
  // The old timer was due at 60 seconds; the new one is due at 90 seconds.
  await clock.advance(30_000)
  expect(runs).toEqual(initial)
  await clock.advance(29_999)
  expect(runs).toEqual(initial)
  await clock.advance(1)
  expect(runs).toEqual([...initial, helperCall(BASSO, 1, '0.2')])
  await clock.advance(120_000)
  expect(runs).toEqual([...initial, ...Array(3).fill(helperCall(BASSO, 1, '0.2'))])
})

test('a silent foreground completion also cancels an old away reminder', async ($, on) => {
  const fixture = record(on, 0, '600 0 0')
  await $.turn.complete({ ...turn, reason: 'answer' })
  await fixture.clock.advance(30_000)
  fixture.state = '5 0 1'
  await $.turn.complete({ ...turn, reason: 'answer', turnId: 't2' })
  expect(fixture.runs).toEqual([helperCall(GLASS, 3, '0.2')])
  fixture.state = '600 0 0'
  await fixture.clock.advance(600_000)
  expect(fixture.runs).toEqual([helperCall(GLASS, 3, '0.2')])
})

const unavailableStates: [string, State][] = [
  ['a nonzero exit status', { exitCode: 1, stdout: '600 1 1' }],
  ['an invalid idle value', 'unavailable 0 1'],
  ['an exception', new Error('state query unavailable')],
]
for (const [label, state] of unavailableStates) {
  test(`stops an active reminder when the state query returns ${label}`, async ($, on) => {
    const fixture = record(on, 0, '600 0 0')
    await $.turn.complete({ ...turn, reason: 'answer' })
    fixture.state = state
    await fixture.clock.advance(60_000)
    expect(fixture.runs).toEqual([helperCall(GLASS, 3, '0.2')])
    fixture.state = '600 0 0'
    await fixture.clock.advance(600_000)
    expect(fixture.runs).toEqual([helperCall(GLASS, 3, '0.2')])
    expect(fixture.stateQueries.length).toBe(2)
  })

  test(`uses the normal notification when the state query returns ${label}`, async ($, on) => {
    const { runs, stateQueries, clock } = record(on, 0, state)
    await $.turn.complete({ ...turn, reason: 'answer' })
    expect(stateQueries).toEqual([[expect.stringMatching(/\/bin\/turn-ding$/), 'state']])
    expect(runs).toEqual([helperCall(GLASS, 3, '0.4')])
    await clock.advance(600_000)
    expect(runs).toEqual([helperCall(GLASS, 3, '0.4')])
  })
}
