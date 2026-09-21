import { useState, type ReactNode } from 'react'
import type { CaseReport, EvidenceLink } from '../api/types'
import { money, verdictLabel, verdictTone, words } from './format'
import { useRunPanels } from './RunContext'
import { openPlanItems } from './store'

export function Conclusion() {
  const { view } = useRunPanels()
  const [open, setOpen] = useState(true)

  if (!view.report) return <LiveStatus />

  const { verdict, headline } = view.report
  const tone = verdictTone[verdict]
  return (
    <section aria-label="Conclusion" className="border-t bg-vellum">
      <div className={`flex items-start gap-4 border-l-8 px-4 py-3 sm:px-6 ${tone.band}`}>
        <div className="min-w-0 flex-1">
          <p className={`font-serif text-2xl font-semibold ${tone.text}`}>{verdictLabel[verdict]}</p>
          <p className="mt-0.5 font-serif text-lg leading-snug">{headline}</p>
        </div>
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="cursor-pointer rounded-sm border px-3 py-1.5 text-sm hover:border-ink"
        >
          {open ? 'Hide details' : 'Show details'}
        </button>
      </div>
      {open && <ReportBody report={view.report} />}
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

function ReportBody({ report }: { report: CaseReport }) {
  return (
    <div className="max-h-[34vh] space-y-6 overflow-y-auto px-4 pt-2 pb-6 sm:px-6">
      <Block title="Summary">
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

      <Block title="Transactions">
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
              <EvidenceChips links={t.evidence} />
            </li>
          ))}
        </ul>
      </Block>

      <Block title="Hypotheses">
        <ul className="space-y-3">
          {report.hypotheses.map((h) => (
            <li key={h.hypothesis} className="max-w-3xl">
              <p className="text-sm leading-relaxed">
                <span className={`font-semibold ${h.status === 'accepted' ? 'text-accepted' : 'text-rejected'}`}>
                  {h.status === 'accepted' ? 'Accepted' : 'Rejected'}:
                </span>{' '}
                {h.hypothesis}. {h.why}
              </p>
              <EvidenceChips links={h.evidence} />
            </li>
          ))}
        </ul>
      </Block>

      <div className="grid gap-6 md:grid-cols-2">
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

      <Block title="Letter to the cardholder">
        <p className="max-w-2xl font-serif text-[1.05rem] leading-relaxed whitespace-pre-line">
          {report.cardholder_letter}
        </p>
      </Block>
    </div>
  )
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
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
function EvidenceChips({ links }: { links: EvidenceLink[] }) {
  const { showEvidence } = useRunPanels()
  return (
    <ul className="mt-1.5 flex flex-wrap gap-1.5">
      {links.map((link) => (
        <li key={`${link.claim}-${link.node_ids.join()}`}>
          <button
            type="button"
            onClick={() => showEvidence(link)}
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
