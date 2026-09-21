import type { ReactNode } from 'react'
import type { PlanItem } from '../api/types'
import { Capsule, type Tone } from './Capsule'
import { Fields, Json, Prose, Ref, Refs } from './Fields'
import { words } from './format'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const list = (value: unknown): Record<string, unknown>[] => (Array.isArray(value) ? value.filter(isRecord) : [])
const strings = (value: unknown): string[] => (Array.isArray(value) ? value.map(String) : [])

/** The fields of a structured model answer that a reader wants first, in reading order. */
const CARDS: { key: string; tone: Tone; title: string }[] = [
  { key: 'headline', tone: 'reason', title: 'Headline' },
  { key: 'reasoning', tone: 'reason', title: 'Reasoning' },
  { key: 'rationale', tone: 'reason', title: 'Rationale' },
  { key: 'executive_summary', tone: 'reason', title: 'Summary' },
  { key: 'detailed_reasoning', tone: 'reason', title: 'Detailed reasoning' },
  { key: 'action', tone: 'next', title: 'Next step' },
  { key: 'suggested_next', tone: 'next', title: 'Suggested next steps' },
  { key: 'plan', tone: 'plan', title: 'Plan' },
  { key: 'plan_edits', tone: 'plan', title: 'Plan edits' },
  { key: 'hypotheses', tone: 'hypo', title: 'Hypotheses' },
  { key: 'hypothesis_updates', tone: 'hypo', title: 'Hypothesis updates' },
  { key: 'facts', tone: 'facts', title: 'Facts found' },
  { key: 'summary', tone: 'facts', title: 'Investigation summary' },
  { key: 'flip_fact', tone: 'next', title: 'What would change the decision' },
]
const CARD_KEYS = new Set(CARDS.map((card) => card.key))
const REFERENCE_KEYS = ['node_ids', 'edge_ids']

const STATUS_MARK: Record<string, string> = { done: '✓', waived: '–' }

export function PlanChecklist({ plan }: { plan: PlanItem[] }) {
  return (
    <ul className="space-y-1">
      {plan.map((item) => (
        <li key={item.id} className="flex gap-2">
          <span aria-label={item.status} className="w-4 shrink-0 text-graphite">
            {STATUS_MARK[item.status] ?? '○'}
          </span>
          <span className={item.status === 'open' ? '' : 'text-graphite'}>
            <span className="id-chip mr-1 text-graphite">{item.id}</span>
            {item.question}
          </span>
        </li>
      ))}
    </ul>
  )
}

function PlanEdits({ edits }: { edits: Record<string, unknown>[] }) {
  if (!edits.length) return <p className="text-graphite">No plan changes.</p>

  return (
    <ul className="space-y-2">
      {edits.map((edit, index) => {
        const item = isRecord(edit.item) ? edit.item : null
        const text = edit.question ?? item?.question ?? edit.waiver_reason
        return (
          <li key={index}>
            <p>
              <span className="mr-1.5 rounded-full bg-plan/12 px-2 py-px text-xs font-medium text-plan">{words(String(edit.operation))}</span>
              <span className="id-chip mr-1 text-graphite">{String(edit.plan_item_id ?? item?.id ?? '')}</span>
              {text ? String(text) : null}
            </p>
            {Array.isArray(edit.evidence_refs) && edit.evidence_refs.length > 0 && (
              <div className="mt-1">
                <Fields value={edit.evidence_refs} />
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

/** Evidence for or against a hypothesis: a signed marker, then the sentence; long lists fold. */
function Evidence({ sign, items }: { sign: '+' | '−'; items: string[] }) {
  if (!items.length) return null
  const row = (text: string, index: number) => (
    <li key={index} className="flex gap-1.5">
      <span aria-label={sign === '+' ? 'for' : 'against'} className={`w-3 shrink-0 text-center font-semibold ${sign === '+' ? 'text-accepted' : 'text-rejected'}`}>
        {sign}
      </span>
      <span className="min-w-0">
        <Prose>{text}</Prose>
      </span>
    </li>
  )
  return (
    <ul className="mt-1.5 space-y-1 text-[0.8125rem] leading-snug">
      {items.slice(0, 3).map(row)}
      {items.length > 3 && (
        <li className="pl-[1.125rem]">
          <details>
            <summary className="cursor-pointer text-xs text-graphite">{items.length - 3} more</summary>
            <ul className="mt-1 space-y-1">{items.slice(3).map((text, index) => row(text, index + 3))}</ul>
          </details>
        </li>
      )}
    </ul>
  )
}

/** Claims the adjudicator cites for a verdict or hypothesis: the sentence, then the graph items it rests on. */
function Claims({ links }: { links: Record<string, unknown>[] }) {
  return (
    <ul className="mt-1.5 space-y-1.5 text-[0.8125rem] leading-snug">
      {links.map((link, index) => (
        <li key={index} className="flex gap-1.5">
          <span aria-hidden className="w-3 shrink-0 text-center text-graphite">
            ◆
          </span>
          <span className="min-w-0">
            <Prose>{String(link.claim ?? '')}</Prose>
            <span className="mt-0.5 block">
              <Refs ids={[...strings(link.node_ids), ...strings(link.edge_ids)]} max={4} />
            </span>
          </span>
        </li>
      ))}
    </ul>
  )
}

const VERDICT_PILL: Record<string, string> = {
  accepted: 'bg-accepted/12 text-accepted',
  rejected: 'bg-rejected/10 text-rejected',
}

/** Working hypotheses (label, status, for and against) and the adjudicator's final ones (claim, verdict, why, evidence). */
function Hypotheses({ items }: { items: Record<string, unknown>[] }) {
  return (
    <ul className="stack">
      {items.map((item, index) => {
        const status = String(item.status ?? '')
        return (
          <li key={index}>
            <div className="flex items-start justify-between gap-2">
              <p className="leading-snug font-medium">{String(item.label ?? item.hypothesis ?? '')}</p>
              <span className={`shrink-0 rounded-full px-2 py-px text-xs ${VERDICT_PILL[status] ?? 'bg-hypo/12 text-hypo'}`}>
                {words(status)}
              </span>
            </div>
            {typeof item.why === 'string' && (
              <p className="mt-1 text-[0.8125rem] leading-snug text-graphite">
                <Prose>{item.why}</Prose>
              </p>
            )}
            <Evidence sign="+" items={strings(item.support)} />
            <Evidence sign="−" items={strings(item.against)} />
            <Claims links={list(item.evidence)} />
          </li>
        )
      })}
    </ul>
  )
}

/** What was found: the statement, with the graph items it rests on underneath. */
function FactList({ facts }: { facts: unknown[] }) {
  return (
    <ul className="stack">
      {facts.map((fact, index) => {
        const record = isRecord(fact) ? fact : { statement: String(fact) }
        const refs = [...strings(record.node_ids), ...strings(record.edge_ids)]
        return (
          <li key={index}>
            <p className="leading-snug">
              <Prose>{String(record.statement ?? '')}</Prose>
            </p>
            {refs.length > 0 && (
              <div className="mt-1">
                <Refs ids={refs} />
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function Marked({ mark, tone, items }: { mark: string; tone: string; items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((text, index) => (
        <li key={index} className="flex gap-2 leading-snug">
          <span aria-hidden className={`w-3 shrink-0 text-center font-semibold ${tone}`}>
            {mark}
          </span>
          <span className="min-w-0">
            <Prose>{text}</Prose>
          </span>
        </li>
      ))}
    </ul>
  )
}

function Part({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <section>
      <h4 className="mb-1.5 flex items-baseline gap-1.5 text-xs font-semibold text-graphite">
        {title}
        <span className="rounded-full bg-paper px-1.5 font-normal tabular-nums">{count}</span>
      </h4>
      {children}
    </section>
  )
}

/** The supervisor's running picture of the case, one part per kind of thing it tracks. */
function InvestigationSummary({ summary }: { summary: Record<string, unknown> }) {
  const hypotheses = list(summary.hypotheses)
  const facts = Array.isArray(summary.key_facts) ? summary.key_facts : []
  const questions = strings(summary.open_questions)
  const contradictions = strings(summary.contradictions)
  return (
    <div className="stack">
      {hypotheses.length > 0 && (
        <Part title="Hypotheses" count={hypotheses.length}>
          <Hypotheses items={hypotheses} />
        </Part>
      )}
      {facts.length > 0 && (
        <Part title="Key facts" count={facts.length}>
          <FactList facts={facts} />
        </Part>
      )}
      {questions.length > 0 && (
        <Part title="Open questions" count={questions.length}>
          <Marked mark="?" tone="text-plan" items={questions} />
        </Part>
      )}
      {contradictions.length > 0 && (
        <Part title="Contradictions" count={contradictions.length}>
          <Marked mark="!" tone="text-rejected" items={contradictions} />
        </Part>
      )}
    </div>
  )
}

/** The supervisor's decision: delegate tasks to roles, or move on to the final decision. */
function NextStep({ action }: { action: Record<string, unknown> }) {
  const tasks = list(action.tasks)
  if (!tasks.length)
    return (
      <>
        <p className="mb-1 font-medium">Decide</p>
        <Fields value={action.reason ?? 'No reason given.'} />
      </>
    )
  return (
    <>
      <p className="mb-2 font-medium">
        Delegate {tasks.length} {tasks.length === 1 ? 'task' : 'tasks'}
      </p>
      <ol className="space-y-2">
        {tasks.map((task, index) => {
          const instructions = typeof task.instructions === 'string' ? task.instructions : ''
          const planItemIds = strings(task.plan_item_ids)
          return (
            <li key={index} className="rounded-sm border border-next/25 bg-vellum px-2.5 py-1.5">
              <p className="font-medium">
                {words(String(task.role))}
                {instructions && (
                  <span className="ml-1.5 rounded-sm border border-agent px-1 text-xs font-normal text-agent">invented role</span>
                )}
              </p>
              <p>{String(task.objective ?? '')}</p>
              {planItemIds.length > 0 && (
                <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-graphite">
                  Answers
                  {planItemIds.map((id) => (
                    <Ref key={id} id={id} />
                  ))}
                </p>
              )}
              {instructions && <p className="mt-1 text-xs text-graphite">{instructions}</p>}
            </li>
          )
        })}
      </ol>
    </>
  )
}

function cardBody(key: string, value: unknown): ReactNode {
  if (key === 'action' && isRecord(value)) return <NextStep action={value} />
  if (key === 'plan' && list(value).every((item) => 'question' in item)) return <PlanChecklist plan={value as PlanItem[]} />
  if (key === 'hypotheses' || key === 'hypothesis_updates') return <Hypotheses items={list(value)} />
  if (key === 'plan_edits') return <PlanEdits edits={list(value)} />
  if (key === 'facts' && Array.isArray(value)) return <FactList facts={value} />
  if (key === 'summary' && isRecord(value)) return <InvestigationSummary summary={value} />
  if (key === 'suggested_next' && Array.isArray(value)) return <Marked mark="›" tone="text-next" items={strings(value)} />
  return <Fields value={value} />
}

const count = (value: unknown) => (Array.isArray(value) ? value.length : undefined)

/**
 * What the model answered, as coloured cards for the parts a reader checks first (reasoning, next step,
 * plan, hypotheses, facts), then everything else, then the exact JSON.
 */
export function ModelOutput({ output, schema }: { output: unknown; schema: string | null }) {
  if (!isRecord(output))
    return (
      <Capsule strong tone="model" title="Model output" pill={schema} open>
        {output == null ? <p className="text-graphite">No output recorded.</p> : <Json value={output} />}
      </Capsule>
    )

  const cards = CARDS.filter((card) => output[card.key] != null)
  const rest = Object.fromEntries(Object.entries(output).filter(([key]) => !CARD_KEYS.has(key) && !REFERENCE_KEYS.includes(key)))
  const references = Object.fromEntries(REFERENCE_KEYS.filter((key) => count(output[key])).map((key) => [key, output[key]]))

  return (
    <Capsule strong tone="model" title="Model output" pill={schema} open>
      <div className="space-y-2">
        {cards.map(({ key, tone, title: cardTitle }) => (
          <Capsule key={key} tone={tone} title={cardTitle} pill={count(output[key])} open>
            {cardBody(key, output[key])}
          </Capsule>
        ))}
        {Object.keys(rest).length > 0 && (
          <Capsule tone="input" title="Other fields" open={cards.length === 0}>
            <Fields value={rest} />
          </Capsule>
        )}
        {Object.keys(references).length > 0 && (
          <Capsule tone="input" title="Graph items cited" pill={Object.values(references).flat().length}>
            <Fields value={references} />
          </Capsule>
        )}
        <Capsule tone="input" title="Raw JSON">
          <Json value={output} />
        </Capsule>
      </div>
    </Capsule>
  )
}
