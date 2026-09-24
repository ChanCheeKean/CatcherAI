import { describe, expect, it } from 'vitest'
import { event } from './fixtures'
import { clock, eventsBy, milestones, replayTimes } from './replay'

const at = (seconds: number) => ({ ts_wall: new Date(Date.UTC(2026, 8, 21, 10, 0, seconds)).toISOString() })

describe('replay clock', () => {
  it('shortens long waits and halves the rest, so a replay keeps moving', () => {
    const events = [event('run_started', 'runtime', {}, at(0)), event('triage', 'triage', {}, at(1)), event('decision', 'adjudicator', {}, at(61))]
    expect(replayTimes(events)).toEqual([0, 500, 1500])
  })

  it('counts the events that have happened by a point in time', () => {
    const times = [0, 500, 500, 1500]
    expect(eventsBy(times, -1)).toBe(0)
    expect(eventsBy(times, 0)).toBe(1)
    expect(eventsBy(times, 500)).toBe(3)
    expect(eventsBy(times, 9999)).toBe(4)
  })

  it('reads as minutes and seconds', () => {
    expect(clock(335_400)).toBe('5:35')
    expect(clock(4_000)).toBe('0:04')
  })
})

describe('milestones', () => {
  it('marks triage, each delegation, a decision sent back and the verdict', () => {
    const marks = milestones([
      event('node_exited', 'triage', { output: {} }),
      event('delegation_started', 'policy_analyst', { task: {} }),
      event('tool_call', 'graph_query', {}),
      event('edge_taken', 'supervisor', { source: 'supervisor', target: 'supervisor', reason: 'open items' }),
      event('decision', 'adjudicator', {}),
    ])
    expect(marks.map((m) => [m.kind, m.index])).toEqual([['start', 0], ['delegation', 1], ['sent-back', 3], ['verdict', 4]])
    expect(marks[1].label).toBe('Supervisor delegates to the policy analyst')
  })
})
