import type { GraphEdge, GraphNode } from '../api/types'
import { Fields } from './Fields'
import { Icon } from './GraphIcon'
import { caption, isAgentWritten, labelStyle } from './graphModel'
import { useRunPanels } from './RunContext'

const MAX_EVENTS = 100
const TIME_KEYS = new Set(['valid_from', 'valid_to'])

const validity = (edge: GraphEdge) =>
  edge.properties.valid_from || edge.properties.valid_to
    ? `${edge.properties.valid_from || 'always'} to ${edge.properties.valid_to || 'now'}`
    : null

function IdButton({ id, label }: { id: string; label?: string }) {
  const { select } = useRunPanels()
  return (
    <button type="button" onClick={() => select({ kind: 'node', id })} className="id-chip cursor-pointer underline-offset-2 hover:underline">
      {label ?? id}
    </button>
  )
}

/** A node or edge of the evidence graph: what it is, how it connects, who found it, and the events behind it. */
export function GraphItemPanel({ id }: { id: string }) {
  const { view, graph } = useRunPanels()
  const node = graph.nodes.get(id)
  const edge = graph.edges.get(id)
  const found = view.touched.get(id)
  const events = view.events.filter((e) => e.refs.includes(id))

  return (
    <>
      {node && <NodeHeader node={node} />}
      {edge && <EdgeHeader edge={edge} />}
      {!node && !edge && <h2 className="id-chip mb-2 text-sm font-semibold">{id}</h2>}
      {found ? (
        <p className="mb-3 text-sm text-graphite">
          Found by {found.actor} with {found.tool} in turn {found.turn}.
        </p>
      ) : (
        (node || edge) && <p className="mb-3 text-sm text-graphite">Context only: no agent has touched this yet.</p>
      )}
      {node && <NodeEdges node={node} />}
      {events.length > 0 && (
        <section className="mt-4">
          <h3 className="mb-1.5 text-sm font-semibold">Events that touched it</h3>
          <ol className="space-y-1.5">
            {events.slice(-MAX_EVENTS).map((event) => (
              <li key={event.seq}>
                <details className="rounded-sm border bg-paper">
                  <summary className="cursor-pointer px-2 py-1 text-sm">
                    <span className="text-graphite tabular-nums">{event.seq}</span> {event.summary}
                  </summary>
                  <pre className="id-chip overflow-x-auto border-t p-2 whitespace-pre-wrap">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </details>
              </li>
            ))}
          </ol>
        </section>
      )}
    </>
  )
}

function NodeHeader({ node }: { node: GraphNode }) {
  return (
    <>
      <div className="mb-1 flex items-center gap-2">
        <span
          className="flex size-7 shrink-0 items-center justify-center rounded-full text-white"
          style={{ background: labelStyle(node.label).color }}
        >
          <Icon label={node.label} />
        </span>
        <div className="min-w-0">
          <h2 className="truncate font-semibold">{node.label}</h2>
          <p className="id-chip text-graphite">{node.id}</p>
        </div>
        {isAgentWritten(node) && <span className="ml-auto rounded-sm border border-agent px-1 text-xs text-agent">agent-written</span>}
      </div>
      <div className="my-3 text-sm">
        <Fields value={node.properties} />
      </div>
    </>
  )
}

function EdgeHeader({ edge }: { edge: GraphEdge }) {
  const { graph } = useRunPanels()
  const valid = validity(edge)
  const end = (id: string) => {
    const other = graph.nodes.get(id)
    return <IdButton id={id} label={other ? `${other.label} ${caption(other)}` : id} />
  }
  return (
    <>
      <h2 className="font-semibold">{edge.type}</h2>
      <p className="id-chip mb-2 text-graphite">{edge.id}</p>
      <p className="mb-2 flex flex-wrap items-center gap-1.5 text-sm">
        {end(edge.src)} <span aria-label="to">to</span> {end(edge.dst)}
      </p>
      {valid && <p className="mb-2 text-sm">Valid {valid}</p>}
      <div className="my-3 text-sm">
        <Fields value={Object.fromEntries(Object.entries(edge.properties).filter(([key]) => !TIME_KEYS.has(key)))} />
      </div>
    </>
  )
}

function NodeEdges({ node }: { node: GraphNode }) {
  const { graph } = useRunPanels()
  const around = [...graph.edges.values()].filter((e) => e.src === node.id || e.dst === node.id)
  if (!around.length) return <p className="text-sm text-graphite">No connections loaded. Double-click the node to expand it.</p>
  return (
    <section>
      <h3 className="mb-1.5 text-sm font-semibold">Connections ({around.length})</h3>
      <ul className="space-y-1.5 text-sm">
        {around.map((edge) => {
          const out = edge.src === node.id
          const otherId = out ? edge.dst : edge.src
          const other = graph.nodes.get(otherId)
          const valid = validity(edge)
          return (
            <li key={edge.id} className="rounded-sm border bg-paper px-2 py-1">
              <div className="flex flex-wrap items-baseline gap-x-1.5">
                <IdButton id={edge.id} label={edge.type} />
                <span className="text-graphite">{out ? 'to' : 'from'}</span>
                <IdButton id={otherId} label={other ? `${other.label} ${caption(other)}` : otherId} />
              </div>
              {valid && <p className="text-xs text-graphite">{valid}</p>}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
