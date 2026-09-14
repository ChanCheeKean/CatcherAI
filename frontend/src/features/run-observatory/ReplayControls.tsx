import { useEffect, useState } from 'react'

export interface ReplayFilters { type: string; actor: string; text: string }

export function ReplayControls({ cursor, maxSeq, live, filters, onCursor, onLive, onFilters }: { cursor: number; maxSeq: number; live: boolean; filters: ReplayFilters; onCursor: (seq: number) => void; onLive: () => void; onFilters: (filters: ReplayFilters) => void }) {
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [bookmarks, setBookmarks] = useState<number[]>([])
  const activePlaying = playing && cursor < maxSeq

  useEffect(() => {
    if (!activePlaying || live) return
    const delay = speed === 0 ? 0 : 500 / speed
    const timer = window.setTimeout(() => onCursor(speed === 0 ? maxSeq : Math.min(maxSeq, cursor + 1)), delay)
    return () => window.clearTimeout(timer)
  }, [activePlaying, cursor, live, maxSeq, onCursor, speed])

  return <div className="border-b border-border bg-surface-1 px-3 py-2">
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={() => onCursor(Math.max(0, cursor - 1))} className="replay-button" aria-label="Previous event">|◀</button>
      <button type="button" onClick={() => { if (live) onCursor(cursor); setPlaying((value) => !value) }} className="replay-button">{activePlaying ? 'Pause' : 'Play'}</button>
      <button type="button" onClick={() => onCursor(Math.min(maxSeq, cursor + 1))} className="replay-button" aria-label="Next event">▶|</button>
      <button type="button" onClick={onLive} className={`replay-button ${live ? 'text-cyan' : ''}`}>Live follow</button>
      <select aria-label="Replay speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))} className="replay-input"><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option><option value={0}>instant</option></select>
      <span className="font-mono text-xs text-ink-faint">seq {cursor}/{maxSeq}</span>
      <input aria-label="Seek sequence" type="range" min={0} max={Math.max(maxSeq, 1)} value={cursor} onChange={(event) => onCursor(Number(event.target.value))} className="min-w-32 flex-1 accent-cyan" />
      <button type="button" onClick={() => setBookmarks((items) => items.includes(cursor) ? items.filter((seq) => seq !== cursor) : [...items, cursor].sort((a, b) => a - b))} className="replay-button">{bookmarks.includes(cursor) ? '★' : '☆'} bookmark</button>
    </div>
    <div className="mt-2 flex flex-wrap gap-2">
      <input aria-label="Filter event type" placeholder="event type" value={filters.type} onChange={(event) => onFilters({ ...filters, type: event.target.value })} className="replay-input" />
      <input aria-label="Filter actor" placeholder="actor" value={filters.actor} onChange={(event) => onFilters({ ...filters, actor: event.target.value })} className="replay-input" />
      <input aria-label="Filter event text" placeholder="search summary or ref" value={filters.text} onChange={(event) => onFilters({ ...filters, text: event.target.value })} className="replay-input min-w-48" />
      {bookmarks.map((seq) => <button type="button" key={seq} onClick={() => onCursor(seq)} className="font-mono text-xs text-amber">★ {seq}</button>)}
    </div>
  </div>
}
