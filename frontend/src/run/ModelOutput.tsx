import type { ReactNode } from 'react'
import type { PlanItem } from '../api/types'
import { Capsule, type Tone } from './Capsule'
import { Fields, Json } from './Fields'
import { words } from './format'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const list = (value: unknown): Record<string, unknown>[] => (Array.isArray(value) ? value.filter(isRecord) : [])

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

function Hypotheses({ items }: { items: Record<string, unknown>[] }) {
  return (
    <ul className="space-y-2.5">
      {items.map((item, index) => (
        <li key={index}>
          <p className="font-medium">
            {String(item.label ?? '')}{' '}
            <span className="ml-1 rounded-full bg-hypo/12 px-2 py-px text-xs font-normal text-hypo">{words(String(item.status ?? ''))}</span>
          </p>
          {['support', 'against'].map((side) =>
            Array.isArray(item[side]) && item[side].length ? (
              <div key={side} className="mt-1 pl-2">
                <p className="text-xs font-medium text-graphite">{side === 'support' ? 'For' : 'Against'}</p>
                <Fields value={item[side]} />
              </div>
            ) : null,
          )}
        </li>
      ))}
    </ul>
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
          return (
            <li key={index} className="rounded-sm border border-next/25 bg-vellum px-2.5 py-1.5">
              <p className="font-medium">
                {words(String(task.role))}
                {instructions && (
                  <span className="ml-1.5 rounded-sm border border-agent px-1 text-xs font-normal text-agent">invented role</span>
                )}
              </p>
              <p>{String(task.objective ?? '')}</p>
              {Array.isArray(task.plan_item_ids) && task.plan_item_ids.length > 0 && (
                <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-graphite">
                  Plan items <Fields value={task.plan_item_ids} />
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
