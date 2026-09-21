import { useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import type { CaseReport, EvidenceLink } from '../api/types'
import { money, verdictLabel, verdictTone, words } from './format'
import { useRunPanels } from './RunContext'
import { openPlanItems } from './store'

const HEIGHT_KEY = 'disputeai.report-height'
/** Open heights (share of the window) the handle cycles through on double-click, then back to collapsed. */
const OPEN_SHARES = [0.34, 0.66]
const MAX_SHARE = 0.75
const KEY_STEP = 40
const COLLAPSE_BELOW = 48

function savedHeight(): number {
  try {
    const saved = Number(localStorage.getItem(HEIGHT_KEY))
    if (saved > 0) return saved
  } catch {
    // storage can be blocked; fall back to the default
  }
  return Math.round(window.innerHeight * OPEN_SHARES[0])
}

const SECTIONS = [
  { id: 'report-summary', label: 'Summary' },
  { id: 'report-transactions', label: 'Transactions' },
  { id: 'report-hypotheses', label: 'Hypotheses' },
  { id: 'report-context', label: 'Decoys and policy' },
  { id: 'report-letter', label: 'Letter' },
]

export function Conclusion() {
  const { view, showEvidence } = useRunPanels()
  /** Height of the report area in px; 0 leaves only the verdict strip. Remembers the last open height. */
  const [height, setHeight] = useState(savedHeight)
  const lastOpen = useRef(height)
  const scroller = useRef<HTMLDivElement>(null)

  if (!view.report) return <LiveStatus />

  const resize = (next: number) => {
    const clamped = Math.max(0, Math.min(next, window.innerHeight * MAX_SHARE))
    const value = clamped < COLLAPSE_BELOW ? 0 : Math.round(clamped)
    setHeight(value)
    if (value === 0) return
    lastOpen.current = value
    try {
      localStorage.setItem(HEIGHT_KEY, String(value))
    } catch {
      // the height just is not remembered
    }
  }
  const drag = (event: PointerEvent<HTMLDivElement>) => {
    const startY = event.clientY
    const startHeight = height
    const handle = event.currentTarget
    handle.setPointerCapture(event.pointerId)
    const move = (moved: globalThis.PointerEvent) => resize(startHeight + startY - moved.clientY)
    const stop = () => {
      handle.removeEventListener('pointermove', move)
      handle.removeEventListener('pointerup', stop)
    }
    handle.addEventListener('pointermove', move)
    handle.addEventListener('pointerup', stop)
  }
  const nudge = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowUp') resize(height + KEY_STEP)
    else if (event.key === 'ArrowDown') resize(height - KEY_STEP)
    else return
    event.preventDefault()
  }
  const nextSnap = () => {
    const snaps = OPEN_SHARES.map((share) => share * window.innerHeight)
    resize(snaps.find((px) => px > height + 8) ?? 0)
  }
  /** A chip asks to show the graph, so the report steps aside; "Show details" brings it back. */
  const reveal = (link: Pick<EvidenceLink, 'node_ids' | 'edge_ids'>) => {
    showEvidence(link)
    setHeight(0)
  }
  const jump = (id: string) => {
    const box = scroller.current
    const target = box?.querySelector<HTMLElement>(`#${id}`)
    if (!box || !target) return
    const offset = target.getBoundingClientRect().top - box.getBoundingClientRect().top
    box.scrollTo({ top: box.scrollTop + offset, behavior: 'smooth' })
  }

  const { verdict, headline } = view.report
  const tone = verdictTone[verdict]
  return (
    <section aria-label="Conclusion" className="flex flex-col border-t bg-vellum">
      <div
        role="separator"
        aria-orientation="horizontal"
        aria-label="Resize report"
        aria-valuenow={height}
        tabIndex={0}
        onPointerDown={drag}
        onKeyDown={nudge}
        onDoubleClick={nextSnap}
        className="group -mt-1.5 flex h-3 shrink-0 cursor-ns-resize touch-none items-center justify-center"
      >
        <span className="h-1 w-12 rounded-full bg-rule transition-colors group-hover:bg-graphite group-focus-visible:bg-ink" />
      </div>
      <div className={`flex items-start gap-4 border-l-8 px-4 py-3 sm:px-6 ${tone.band}`}>
        <div className="min-w-0 flex-1">
          <p className={`font-serif text-2xl font-semibold ${tone.text}`}>{verdictLabel[verdict]}</p>
          <p className="mt-0.5 font-serif text-lg leading-snug">{headline}</p>
        </div>
        <button
          type="button"
          aria-expanded={height > 0}
          onClick={() => resize(height ? 0 : lastOpen.current)}
          className="cursor-pointer rounded-sm border px-3 py-1.5 text-sm hover:border-ink"
        >
          {height ? 'Hide details' : 'Show details'}
        </button>
      </div>
      {height > 0 && (
        <div className="flex min-h-0 flex-col" style={{ height, maxHeight: '75vh' }}>
          <nav
            aria-label="Report sections"
            className="flex shrink-0 gap-1 overflow-x-auto border-y bg-paper px-4 py-1.5 sm:px-6"
          >
            {SECTIONS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => jump(id)}
                className="shrink-0 cursor-pointer rounded-full px-3 py-0.5 text-sm text-graphite hover:bg-vellum hover:text-ink"
              >
                {label}
              </button>
            ))}
          </nav>
          <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
            <ReportBody report={view.report} onShow={reveal} />
          </div>
        </div>
      )}
    </section>
  )
}

function LiveStatus() {
  const { view } = useRunPanels()
  const open = openPlanItems(view)
  let text = 'Starting the investigation…'
  if (view.status === 'failed') text = `The run failed: ${view.error}`
  else if (view.events.length)
    text = `Investigating. Supervisor turn ${view.turn}; ${open.length} of ${view.plan.length} plan items still open.`
  return (
    <section aria-label="Conclusion" className="border-t bg-vellum px-4 py-3 text-sm sm:px-6">
      <p className={view.status === 'failed' ? 'text-rejected' : 'text-graphite'} role="status">
        {text}
      </p>
      {view.status === 'running' && open.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5">
          {open.map((item) => (
            <li key={item.id}>{item.question}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

type Reveal = (link: Pick<EvidenceLink, 'node_ids' | 'edge_ids'>) => void

function ReportBody({ report, onShow }: { report: CaseReport; onShow: Reveal }) {
  return (
    <div className="space-y-6 px-4 pt-3 pb-6 sm:px-6">
      <Block id="report-summary" title="Summary">
        <p className="max-w-3xl leading-relaxed">{report.executive_summary}</p>
        <p className="mt-2 text-sm text-graphite">
          {words(report.claim_family)}, {Math.round(report.confidence * 100)}% confident. This would
          change if: {report.flip_fact}
        </p>
      </Block>

      <details className="max-w-3xl">
        <summary className="cursor-pointer font-semibold">Detailed reasoning</summary>
        <p className="mt-2 leading-relaxed whitespace-pre-line">{report.detailed_reasoning}</p>
      </details>

      <Block id="report-transactions" title="Transactions">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-graphite">
              <tr>
                <th className="py-1 pr-3 font-medium">Transaction</th>
                <th className="py-1 pr-3 font-medium">Outcome</th>
                <th className="py-1 pr-3 text-right font-medium">Disputed</th>
                <th className="py-1 pr-3 text-right font-medium">Credited</th>
                <th className="py-1 pr-3 text-right font-medium">Cardholder pays</th>
                <th className="py-1 font-medium">Network action</th>
              </tr>
            </thead>
            <tbody>
              {report.transactions.map((t) => (
                <tr key={t.txn_id} className="border-t align-top">
                  <td className="id-chip py-2 pr-3">{t.txn_id}</td>
                  <td className={`py-2 pr-3 font-medium ${verdictTone[t.verdict].text}`}>
                    {verdictLabel[t.verdict]}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{money(t.disputed_amount)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{money(t.credit_amount)}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{money(t.cardholder_liability)}</td>
                  <td className="py-2">
                    {words(t.network_action)}
                    {t.reason_code && <span className="text-graphite"> ({t.reason_code})</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="mt-3 space-y-3">
          {report.transactions.map((t) => (
            <li key={t.txn_id} className="max-w-3xl">
              <p className="text-sm leading-relaxed">
                <span className="id-chip">{t.txn_id}</span> {t.rationale}
              </p>
              <EvidenceChips links={t.evidence} onShow={onShow} />
            </li>
          ))}
        </ul>
      </Block>

      <Block id="report-hypotheses" title="Hypotheses">
        <ul className="space-y-3">
          {report.hypotheses.map((h) => (
            <li key={h.hypothesis} className="max-w-3xl">
              <p className="text-sm leading-relaxed">
                <span className={`font-semibold ${h.status === 'accepted' ? 'text-accepted' : 'text-rejected'}`}>
                  {h.status === 'accepted' ? 'Accepted' : 'Rejected'}:
                </span>{' '}
                {h.hypothesis}. {h.why}
              </p>
              <EvidenceChips links={h.evidence} onShow={onShow} />
            </li>
          ))}
        </ul>
      </Block>

      <div id="report-context" className="grid gap-6 md:grid-cols-2">
        <TextList title="Decoys ruled out" items={report.decoys_ruled_out} />
        <TextList title="Missing evidence" items={report.missing_evidence} />
        <Block title="Policy basis">
          <ul className="space-y-1.5 text-sm">
            {report.policy_basis.map((c) => (
              <li key={c.document_id}>
                <span className="id-chip">{c.document_id}</span> {c.why}
              </li>
            ))}
          </ul>
        </Block>
        <TextList
          title="Account actions"
          items={report.account_actions.map(
            (a) => `${a.action}${a.target_id ? ` (${a.target_id})` : ''}: ${a.reason}`,
          )}
        />
      </div>

      <Block id="report-letter" title="Letter to the cardholder">
        <p className="max-w-2xl font-serif text-[1.05rem] leading-relaxed whitespace-pre-line">
          {report.cardholder_letter}
        </p>
      </Block>
    </div>
  )
}

function Block({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <div id={id}>
      <h3 className="mb-1.5 font-semibold">{title}</h3>
      {children}
    </div>
  )
}

function TextList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <Block title={title}>
      <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </Block>
  )
}

/** One chip per cited claim; clicking it lights up exactly those nodes and edges in the graph. */
function EvidenceChips({ links, onShow }: { links: EvidenceLink[]; onShow: Reveal }) {
  return (
    <ul className="mt-1.5 flex flex-wrap gap-1.5">
      {links.map((link) => (
        <li key={`${link.claim}-${link.node_ids.join()}`}>
          <button
            type="button"
            onClick={() => onShow(link)}
            title={`${link.node_ids.length} nodes, ${link.edge_ids.length} edges`}
            className="max-w-md cursor-pointer truncate rounded-sm border bg-paper px-2 py-0.5 text-xs hover:bg-highlighter"
          >
            {link.claim}
          </button>
        </li>
      ))}
    </ul>
  )
}
