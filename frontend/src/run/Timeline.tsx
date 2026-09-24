import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { TrajectoryEvent } from '../api/types'
import { clock, eventsBy, milestones, replayTimes, type Milestone, type MilestoneKind } from './replay'

const SPEEDS = [1, 2, 4]
/** Milestones closer than this share of the timeline are one mark: parallel delegations start together. */
const MERGE_SHARE = 0.012

const markTone: Record<MilestoneKind, string> = {
  start: 'bg-graphite',
  delegation: 'bg-agent',
  'sent-back': 'bg-partial',
  verdict: 'bg-ink',
}

interface Mark {
  kind: MilestoneKind
  label: string
  time: number
}

/** One mark per moment; delegations made in the same breath read as one sentence. */
function marksOf(list: Milestone[], times: number[], duration: number): Mark[] {
  const marks: (Mark & { agents: string[] })[] = []
  for (const milestone of list) {
    const time = times[milestone.index]
    const last = marks.at(-1)
    if (last && last.kind === milestone.kind && time - last.time <= duration * MERGE_SHARE) {
      last.agents.push(milestone.label)
      continue
    }
    marks.push({ kind: milestone.kind, label: milestone.label, time, agents: [milestone.label] })
  }
  return marks.map(({ agents, ...mark }) => {
    if (mark.kind !== 'delegation' || agents.length === 1) return mark
    const names = agents.map((label) => label.replace('Supervisor delegates to the ', ''))
    return { ...mark, label: `Supervisor delegates to the ${names.slice(0, -1).join(', ')} and ${names.at(-1)}` }
  })
}

interface TimelineProps {
  events: TrajectoryEvent[]
  /** Called with how many events have happened at the playhead. */
  onCursor: (count: number) => void
  /** Start at the beginning and play, rather than resting on the finished run. */
  autoplay: boolean
}

/** Replay controls for a finished run: play, speed, a scrubber marked with the run's turning points. */
export function Timeline({ events, onCursor, autoplay }: TimelineProps) {
  const times = useMemo(() => replayTimes(events), [events])
  const duration = times.at(-1) ?? 0
  const marks = useMemo(() => marksOf(milestones(events), times, duration), [events, times, duration])
  const [playhead, setPlayhead] = useState(autoplay ? 0 : duration)
  const [playing, setPlaying] = useState(autoplay)
  const [speed, setSpeed] = useState(1)
  const head = useRef(playhead)

  const seek = (time: number) => {
    head.current = Math.max(0, Math.min(duration, time))
    setPlayhead(head.current)
  }

  useEffect(() => {
    if (!playing) return
    let frame = 0
    let last = performance.now()
    const tick = (now: number) => {
      head.current = Math.min(duration, head.current + (now - last) * speed)
      last = now
      setPlayhead(head.current)
      if (head.current >= duration) setPlaying(false)
      else frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing, speed, duration])

  const count = eventsBy(times, playhead)
  useEffect(() => onCursor(count), [count, onCursor])

  const toggle = () => {
    if (!playing && playhead >= duration) seek(0)
    setPlaying(!playing)
  }
  const verdict = marks.find((m) => m.kind === 'verdict')
  const now = [...marks].reverse().find((m) => m.time <= playhead)
  const started = Date.parse(events[0]?.ts_wall ?? '')
  const realAt = count ? Date.parse(events[count - 1].ts_wall) - started : 0
  const realTotal = events.length ? Date.parse(events[events.length - 1].ts_wall) - started : 0
  const share = duration ? playhead / duration : 1

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b bg-vellum px-4 py-2 sm:px-6">
      <button
        type="button"
        onClick={toggle}
        className="w-28 cursor-pointer rounded-sm bg-ink px-3 py-1.5 text-sm font-medium text-vellum"
      >
        {playing ? 'Pause' : playhead >= duration ? 'Replay run' : 'Play'}
      </button>
      <div role="group" aria-label="Replay speed" className="flex overflow-hidden rounded-sm border text-xs">
        {SPEEDS.map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={speed === value}
            onClick={() => setSpeed(value)}
            className="cursor-pointer px-2 py-1 tabular-nums not-first:border-l not-aria-pressed:hover:bg-paper aria-pressed:bg-ink aria-pressed:text-vellum"
          >
            {value}×
          </button>
        ))}
      </div>

      <div className="relative order-last min-w-0 basis-full pb-3 md:order-none md:flex-1 md:basis-auto">
        <input
          type="range"
          aria-label="Replay position"
          aria-valuetext={`${clock(realAt)} of ${clock(realTotal)} run time`}
          min={0}
          max={duration}
          step="any"
          value={playhead}
          onChange={(event) => seek(Number(event.target.value))}
          className="scrubber w-full"
          style={{ '--share': `${share * 100}%` } as CSSProperties}
        />
        {marks.map((mark) => (
          <button
            key={`${mark.kind}-${mark.time}`}
            type="button"
            title={mark.label}
            aria-label={`Jump to: ${mark.label}`}
            onClick={() => seek(mark.time)}
            style={{ left: `${(mark.time / (duration || 1)) * 100}%` }}
            className={`absolute bottom-0 h-2.5 w-1 -translate-x-1/2 cursor-pointer rounded-full hover:scale-y-150 ${markTone[mark.kind]} ${
              mark.time <= playhead ? '' : 'opacity-35'
            }`}
          />
        ))}
      </div>

      <p className="flex min-w-0 items-baseline gap-3 text-sm">
        <span className="tabular-nums">
          {clock(realAt)} <span className="text-graphite">of {clock(realTotal)} run time</span>
        </span>
      </p>
      {verdict && playhead < verdict.time && (
        <button
          type="button"
          onClick={() => {
            setPlaying(false)
            seek(duration)
          }}
          className="cursor-pointer text-sm text-graphite underline-offset-4 hover:text-ink hover:underline"
        >
          Skip to verdict
        </button>
      )}
      <p aria-live="polite" className="basis-full truncate text-sm text-graphite md:order-last">
        {now ? now.label : 'The run starts'}
      </p>
    </div>
  )
}
