import type { Flow, ToolCall, Visit } from './flow'
import { Structured } from './Fields'
import { words } from './format'

const seconds = (ms: number | null) => (ms === null ? 'running' : `${(ms / 1000).toFixed(1)} s`)
const CLIP = 2400

function Call({ call, caller }: { call: ToolCall; caller?: string }) {
  const found = call.nodeIds.length + call.edgeIds.length
  const result = JSON.stringify(call.result, null, 2) ?? ''
  return (
    <details className="rounded-sm border bg-paper">
      <summary className="cursor-pointer px-2 py-1 text-sm">
        <span className="id-chip">{call.tool}</span>
        <span className="text-graphite">
          {caller ? ` by ${caller}, ` : ' '}
          {call.result === null ? 'waiting for result' : `${found} graph items`}
        </span>
      </summary>
      <div className="space-y-2 border-t p-2">
        <pre className="id-chip overflow-x-auto whitespace-pre-wrap">{JSON.stringify(call.args, null, 2)}</pre>
        <pre className="id-chip max-h-60 overflow-auto border-t pt-2 whitespace-pre-wrap">
          {result.length > CLIP ? `${result.slice(0, CLIP)}\n… ${result.length - CLIP} more characters` : result}
        </pre>
      </div>
    </details>
  )
}

const STATUS_MARK: Record<string, string> = { done: '✓', waived: '–' }

function PlanChecklist({ plan }: { plan: NonNullable<Visit['plan']> }) {
  return (
    <ul className="space-y-1 text-sm">
      {plan.map((item) => (
        <li key={item.id} className="flex gap-2">
          <span aria-label={item.status} className="w-4 text-graphite">
            {STATUS_MARK[item.status] ?? '○'}
          </span>
          <span className={item.status === 'open' ? '' : 'text-graphite'}>{item.question}</span>
        </li>
      ))}
    </ul>
  )
}

function VisitSection({ visit, open }: { visit: Visit; open: boolean }) {
  return (
    <details open={open} className="rounded-sm border bg-vellum">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
        Visit {visit.visit}
        <span className="font-normal text-graphite">
          {' '}
          in turn {visit.turn}, {seconds(visit.durationMs)}, {visit.tokens.toLocaleString()} tokens
        </span>
      </summary>
      <div className="border-t px-3 pb-3">
        {visit.exits.length > 0 && <p className="mt-2 text-sm text-graphite">Then: {visit.exits.join('; ')}</p>}
        {visit.skills.length > 0 && (
          <p className="mt-2 text-sm">
            <span className="text-graphite">Skills loaded: </span>
            {visit.skills.join(', ')}
          </p>
        )}
        <Structured title="Input" value={visit.input} />
        <Structured title="Output" value={visit.output} />
        {visit.plan && (
          <section className="mt-3">
            <h4 className="mb-1 text-sm font-semibold">Plan after this turn</h4>
            <PlanChecklist plan={visit.plan} />
          </section>
        )}
        {visit.tools.length > 0 && (
          <section className="mt-3">
            <h4 className="mb-1 text-sm font-semibold">Tool calls ({visit.tools.length})</h4>
            <ol className="space-y-1.5">
              {visit.tools.map((call) => (
                <li key={call.callId}>
                  <Call call={call} />
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </details>
  )
}

/** What one agent node did on every visit, or what every call of one tool did. */
export function ActorPanel({ name, flow }: { name: string; flow: Flow }) {
  const node = flow.nodes.find((n) => n.id === name)
  const isTool = node?.kind === 'tool'
  const visits = flow.visits.get(name) ?? []
  const calls = flow.toolCalls.get(name) ?? []
  const adHoc = node?.adHoc ? ', role invented by the supervisor' : ''

  return (
    <>
      <h2 className={isTool ? 'id-chip text-sm font-semibold' : 'font-semibold'}>{isTool ? name : words(name)}</h2>
      <p className="mb-3 text-sm text-graphite">
        {isTool
          ? `${calls.length} calls`
          : `${visits.length} ${visits.length === 1 ? 'visit' : 'visits'}${adHoc}`}
      </p>
      {visits.length === 0 && calls.length === 0 && <p className="text-sm">Nothing recorded yet.</p>}
      <ol className="space-y-2">
        {visits.map((visit, index) => (
          <li key={`${visit.actor}-${visit.visit}`}>
            <VisitSection visit={visit} open={index === visits.length - 1} />
          </li>
        ))}
        {calls.map((call) => (
          <li key={call.callId}>
            <Call call={call} caller={`${words(call.caller)} (visit ${call.visit})`} />
          </li>
        ))}
      </ol>
    </>
  )
}
