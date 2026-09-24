import { useQueries } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { CaseReport, EvidenceLink, GraphNode } from '../api/types'
import { comparedClauses, decidingSentence, textsCiting } from './clauses'
import { idsIn, isShown } from './evidence'
import { Prose, Ref } from './Fields'
import { categoryLabel, money, verdictLabel, verdictTone, words } from './format'
import { caption, fromNeighbor } from './graphModel'
import { useRunPanels } from './RunContext'

type Link = Pick<EvidenceLink, 'node_ids' | 'edge_ids'>

const SECTIONS = [
  { id: 'report-summary', label: 'Summary' },
  { id: 'report-charges', label: 'Charges' },
  { id: 'report-hypotheses', label: 'Hypotheses' },
  { id: 'report-context', label: 'Decoys' },
  { id: 'report-improvements', label: 'Improvements' },
  { id: 'report-letter', label: 'Letter' },
]

/**
 * The final report, read beside the canvas: every cited claim is a button that lights up its evidence
 * in the graph while the claim stays on screen.
 */
export function Report({ report }: { report: CaseReport }) {
  const confidence = Math.round(report.confidence * 100)
  return (
    <article aria-label="Report" className="space-y-6">
      <nav aria-label="Report sections" className="sticky -top-4 z-10 -mx-4 -mt-4 flex flex-wrap gap-0.5 border-b bg-vellum px-2 py-1.5">
        {SECTIONS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            className="shrink-0 cursor-pointer rounded-full px-2 py-0.5 text-sm text-graphite hover:bg-paper hover:text-ink"
          >
            {label}
          </button>
        ))}
      </nav>

      <Block id="report-summary" title="Summary">
        <p className="leading-relaxed">{report.executive_summary}</p>
        <p className="mt-3 flex items-center gap-2 text-sm">
          <span className="text-graphite">Confidence</span>
          <span aria-hidden className="h-1.5 w-20 overflow-hidden rounded-full bg-rule">
            <span className="block h-full bg-ink" style={{ width: `${confidence}%` }} />
          </span>
          <span className="font-medium tabular-nums">{confidence}%</span>
        </p>
        <aside className="mt-3 border-l-2 border-partial bg-paper/60 py-1.5 pr-2 pl-3 text-sm">
          <p className="font-medium">What would change this decision</p>
          <p className="mt-0.5 leading-relaxed text-graphite">
            <Prose>{report.flip_fact}</Prose>
          </p>
        </aside>
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-semibold">Detailed reasoning</summary>
          <p className="mt-2 text-sm leading-relaxed whitespace-pre-line">{report.detailed_reasoning}</p>
        </details>
      </Block>

      <ClauseComparison report={report} />

      <Block id="report-charges" title="Charges">
        <ul className="space-y-4">
          {report.charges.map((charge) => (
            <li key={charge.charge_id} className="rounded-sm border bg-paper p-3">
              <p className="flex flex-wrap items-baseline gap-x-2">
                <Ref id={charge.charge_id} />
                <span className={`font-medium ${verdictTone[charge.verdict].text}`}>{verdictLabel[charge.verdict]}</span>
                <span className="text-sm text-graphite">{charge.category} · {categoryLabel[charge.category]}</span>
              </p>
              <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
                <Amount label="Disputed" value={charge.disputed_amount} />
                <Amount label="Credit" value={charge.credit_amount} />
                <Amount label="Card Member liability" value={charge.card_member_liability} />
              </dl>
              <p className="mt-2 text-sm leading-relaxed">
                <Prose>{charge.rationale}</Prose>
              </p>
              <Claims links={charge.evidence} />
            </li>
          ))}
        </ul>
      </Block>

      <Block id="report-hypotheses" title="Hypotheses">
        <ul className="space-y-5">
          {[...report.hypotheses]
            .sort((x, y) => Number(y.status === 'accepted') - Number(x.status === 'accepted'))
            .map((h) => {
              const accepted = h.status === 'accepted'
              return (
                <li key={h.hypothesis} className={`border-l-4 pl-3 ${accepted ? 'border-accepted' : 'border-rejected/70'}`}>
                  <p className="flex items-start justify-between gap-3">
                    <span className="font-serif leading-snug font-semibold">{h.hypothesis.replace(/\.$/, '')}</span>
                    <span
                      className={`mt-0.5 shrink-0 rounded-full px-2 py-px text-xs font-medium ${accepted ? 'bg-accepted/12 text-accepted' : 'bg-rejected/10 text-rejected'}`}
                    >
                      {accepted ? 'Accepted' : 'Rejected'}
                    </span>
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-graphite">
                    <Prose>{h.why}</Prose>
                  </p>
                  <Claims links={h.evidence} />
                </li>
              )
            })}
        </ul>
      </Block>

      <div id="report-context" className="space-y-6">
        <Decoys items={report.decoys_ruled_out} />
        <Block title="Policy basis">
          <ul className="stack text-sm">
            {report.policy_basis.map((c) => (
              <li key={c.document_id}>
                <Ref id={c.document_id} />
                <span className="ml-1.5 leading-relaxed text-graphite">
                  <Prose>{c.why}</Prose>
                </span>
              </li>
            ))}
          </ul>
        </Block>
      </div>

      <Block id="report-improvements" title="System Improvements">
        {report.system_improvements.length ? (
          <ul className="stack">
            {report.system_improvements.map((item, index) => (
              <li key={index} className="rounded-sm border bg-paper p-3">
                <span className="rounded-full bg-vellum px-2 py-0.5 text-xs font-medium">{words(item.target)}</span>
                <p className="mt-2 font-medium">{item.issue}</p>
                <p className="mt-1 text-sm text-graphite">{item.suggestion}</p>
                <Claims links={item.evidence} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-graphite">None — the policies were clear and followed.</p>
        )}
      </Block>

      <Block id="report-letter" title="Letter to the Card Member">
        <p className="font-serif leading-relaxed whitespace-pre-line">{report.card_member_letter}</p>
      </Block>
    </article>
  )
}

function Block({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-10">
      <h3 className="mb-2 font-semibold">{title}</h3>
      {children}
    </section>
  )
}

function Amount({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs text-graphite">{label}</dt>
      <dd className="font-medium tabular-nums">{money(value)}</dd>
    </div>
  )
}

/** A button that lights up its evidence in the graph; pressed while the graph shows exactly that evidence. */
function ShowButton({ link, title, className, children }: { link: Link; title: string; className: string; children: ReactNode }) {
  const { showEvidence, highlight } = useRunPanels()
  return (
    <button
      type="button"
      aria-pressed={isShown(highlight, link)}
      onClick={() => showEvidence(link)}
      title={title}
      className={`w-full cursor-pointer rounded-sm border bg-paper text-left hover:border-ink aria-pressed:border-ink ${className}`}
    >
      {children}
    </button>
  )
}

/** A cited claim as one row that shows its evidence. */
function ClaimButton({ link, children }: { link: Link; children: ReactNode }) {
  return (
    <ShowButton
      link={link}
      title={`${link.node_ids.length} nodes, ${link.edge_ids.length} edges`}
      className="flex items-baseline gap-2 px-2 py-1 text-xs leading-snug aria-pressed:bg-highlighter"
    >
      <span aria-hidden className="shrink-0 text-graphite">◆</span>
      <span className="min-w-0">{children}</span>
    </ShowButton>
  )
}

/** One row per cited claim. */
function Claims({ links }: { links: EvidenceLink[] }) {
  if (!links.length) return null
  return (
    <ul className="mt-2 space-y-1">
      {links.map((link) => (
        <li key={`${link.claim}-${link.node_ids.join()}`}>
          <ClaimButton link={link}>{link.claim}</ClaimButton>
        </li>
      ))}
    </ul>
  )
}

/** Each look-alike the report ruled out lights up the records it names. */
function Decoys({ items }: { items: string[] }) {
  const { graph } = useRunPanels()
  if (!items.length) return null
  return (
    <Block title="Decoys ruled out">
      <ul className="space-y-1">
        {items.map((item) => {
          const link = idsIn(item, graph.edges)
          return (
            <li key={item}>
              {link.node_ids.length + link.edge_ids.length ? (
                <ClaimButton link={link}>
                  <Prose>{item}</Prose>
                </ClaimButton>
              ) : (
                <p className="px-2 py-1 text-xs leading-snug text-graphite">{item}</p>
              )}
            </li>
          )
        })}
      </ul>
    </Block>
  )
}

interface Compared {
  clause: GraphNode
  document: GraphNode
  line: string
}

const SIDES = [
  { owner: 'amex', title: 'Amex Policy' },
  { owner: 'merchant', title: 'Merchant Policy' },
]

/**
 * When a policy System Improvement rests on both Amex and Merchant Clauses, set them side by side,
 * each with the line the report leans on highlighted. Each Clause's owner comes from its policy document.
 */
function ClauseComparison({ report }: { report: CaseReport }) {
  const { graph } = useRunPanels()
  const ids = comparedClauses(report)
  const documents = useQueries({
    queries: ids.map((id) => ({ queryKey: ['neighbors', id], queryFn: () => api.neighbors(id), staleTime: Infinity })),
  })
  const compared = ids.flatMap((id, index): Compared[] => {
    const clause = graph.nodes.get(id)
    const hit = documents[index]?.data?.neighbors.find((n) => typeof n.node.owner === 'string')
    const text = clause?.properties.text
    if (!clause || !hit || typeof text !== 'string') return []
    return [{ clause, document: fromNeighbor(id, hit).node, line: decidingSentence(text, textsCiting(report, id)) }]
  })
  const sides = SIDES.map((side) => ({ ...side, clauses: compared.filter((c) => c.document.properties.owner === side.owner) }))
  if (sides.some((side) => !side.clauses.length)) return null

  return (
    <Block id="report-clauses" title="Amex Policy vs Merchant Policy">
      <p className="mb-2 text-sm text-graphite">
        The Clauses this decision weighs against each other. Where a Clause says more than one thing, the line the report quotes or leans on is highlighted.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {sides.map((side) => (
          <div key={side.owner}>
            <h4 className="mb-1.5 text-sm font-semibold">{side.title}</h4>
            <ul className="space-y-2">
              {side.clauses.map((c) => (
                <li key={c.clause.id}>
                  <ClauseCard {...c} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Block>
  )
}

function ClauseCard({ clause, document, line }: Compared) {
  const text = String(clause.properties.text)
  const at = text.indexOf(line)
  return (
    <ShowButton link={{ node_ids: [clause.id], edge_ids: [] }} title={`${clause.label} ${clause.id}`} className="p-2.5">
      <span className="block text-xs text-graphite">{caption(document)}</span>
      <span className="block text-sm font-semibold">{caption(clause)}</span>
      {/* A one-sentence Clause is its own deciding line, so only a longer one gets a mark. */}
      <span className="mt-1 block text-sm leading-relaxed">
        {line === text ? (
          text
        ) : (
          <>
            {text.slice(0, at)}
            <mark className="rounded-[2px] bg-highlighter/70 px-0.5 text-ink">{line}</mark>
            {text.slice(at + line.length)}
          </>
        )}
      </span>
    </ShowButton>
  )
}
