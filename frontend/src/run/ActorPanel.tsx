import { Capsule, Pill } from './Capsule'
import { Fields, Json } from './Fields'
import type { Flow, ToolCall, Visit } from './flow'
import { words } from './format'
import { ModelOutput, PlanChecklist } from './ModelOutput'

const seconds = (ms: number | null) => (ms === null ? 'running' : `${(ms / 1000).toFixed(1)} s`)
const CLIP = 2400

function Call({ call, caller }: { call: ToolCall; caller?: string }) {
  const found = call.nodeIds.length + call.edgeIds.length
  const result = JSON.stringify(call.result, null, 2) ?? ''
  return (
    <Capsule
      tone="tools"
      title={<span className="id-chip">{call.tool}</span>}
      pill={call.result === null ? 'waiting' : `${found} graph items`}
    >
      {caller && <p className="mb-2 text-xs text-graphite">Called by {caller}</p>}
      <p className="mb-1 text-xs font-medium text-graphite">Arguments</p>
      <Json value={call.args} max="max-h-40" />
      <p className="mt-2 mb-1 text-xs font-medium text-graphite">Result</p>
      <pre className="id-chip max-h-60 overflow-auto rounded-sm border bg-paper p-2 whitespace-pre-wrap">
        {result.length > CLIP ? `${result.slice(0, CLIP)}\n… ${result.length - CLIP} more characters` : result}
      </pre>
    </Capsule>
  )
}

function VisitSection({ visit, open }: { visit: Visit; open: boolean }) {
  return (
    <details open={open} className="rounded-md border bg-paper">
      <summary className="flex cursor-pointer flex-wrap items-center gap-1.5 px-3 py-2">
        <span className="mr-1 text-sm font-semibold">Visit {visit.visit}</span>
        <Pill>turn {visit.turn}</Pill>
        <Pill>{seconds(visit.durationMs)}</Pill>
        <Pill>{visit.tokens.toLocaleString()} tokens</Pill>
      </summary>
      <div className="space-y-2 border-t p-2.5">
        {(visit.skills.length > 0 || visit.exits.length > 0) && (
          <div className="flex flex-wrap items-center gap-1.5 px-0.5 text-xs text-graphite">
            {visit.skills.map((skill) => (
              <Pill key={skill}>skill: {skill}</Pill>
            ))}
            {visit.exits.length > 0 && <span>Then: {visit.exits.join('; ')}</span>}
          </div>
        )}

        <ModelOutput output={visit.output} schema={visit.schema} />

        {visit.tools.length > 0 && (
          <Capsule tone="tools" title="Tool calls" pill={visit.tools.length} open={visit.output === null}>
            <ol className="space-y-1.5">
              {visit.tools.map((call) => (
                <li key={call.callId}>
                  <Call call={call} />
                </li>
              ))}
            </ol>
          </Capsule>
        )}
        {visit.plan && (
          <Capsule
            tone="plan"
            title="Plan after this turn"
            pill={`${visit.plan.filter((item) => item.status === 'open').length} open`}
          >
            <PlanChecklist plan={visit.plan} />
          </Capsule>
        )}
        {visit.input != null && (
          <Capsule tone="input" title="Input">
            <div className="space-y-2">
              <Fields value={visit.input} />
              <Capsule tone="input" title="Raw JSON">
                <Json value={visit.input} />
              </Capsule>
            </div>
          </Capsule>
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
        {isTool ? `${calls.length} calls` : `${visits.length} ${visits.length === 1 ? 'visit' : 'visits'}${adHoc}`}
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
