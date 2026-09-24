import type { GraphEdge, GraphNode, GraphOntology } from '../api/types'
import { money, words } from './format'

export type GraphRegion = string
export type IconName = 'person' | 'swap' | 'scroll' | 'flag'
export interface LabelStyle { region: GraphRegion; color: string; icon: IconName }

/** One clearly different hue per region; its labels are tints of it, darkest first, so white icons stay legible. */
const REGION_HUES: Record<string, { hue: number; saturation: number }> = {
  parties: { hue: 216, saturation: 58 },
  commerce: { hue: 28, saturation: 72 },
  terms: { hue: 152, saturation: 48 },
  case: { hue: 342, saturation: 55 },
}
const ICONS: Record<string, IconName> = { parties: 'person', commerce: 'swap', terms: 'scroll', case: 'flag' }
const FALLBACK_COLOR = '#4f5c70'

export const regionColor = (region: GraphRegion) => tint(region, 0, 1)

function tint(region: GraphRegion, index: number, count: number): string {
  const tone = REGION_HUES[region]
  if (!tone) return FALLBACK_COLOR
  const lightness = 34 + (count > 1 ? (index / (count - 1)) * 16 : 0)
  return `hsl(${tone.hue} ${tone.saturation}% ${lightness}%)`
}

export function graphModel(ontology: GraphOntology) {
  const regions = Object.entries(ontology.groups).map(([id, group]) => ({ id, title: group.title }))
  const members = new Map<string, string[]>()
  for (const [label, { group }] of Object.entries(ontology.labels)) {
    if (!members.has(group)) members.set(group, [])
    members.get(group)!.push(label)
  }
  const styles = new Map<string, LabelStyle>()
  for (const [group, labels] of members)
    labels.forEach((label, index) =>
      styles.set(label, { region: group, color: tint(group, index, labels.length), icon: ICONS[group] ?? 'flag' }),
    )
  const last = regions.at(-1)?.id ?? 'case'
  const fallback: LabelStyle = { region: last, color: FALLBACK_COLOR, icon: ICONS[last] ?? 'flag' }
  return { regions, labelStyle: (label: string) => styles.get(label) ?? fallback }
}

/** Keys whose value names the record, in order of preference. */
const NAME_KEYS = ['name', 'title', 'plan', 'label', 'description', 'summary', 'statement']
/** Keys that say what kind of record it is, used when nothing names it. */
const KIND_KEYS = ['kind', 'method']

/**
 * A short human name for a node, derived from whichever properties it has (never from its label):
 * a Card by product and last digits, a clause by number and heading, a message by sender, a named
 * record by its name plus any amount, an unnamed one by amount and kind. Falls back to its text, then the id.
 */
export function caption(node: GraphNode): string {
  const text = (key: string) => {
    const value = node.properties[key]
    return typeof value === 'string' && value ? value : undefined
  }
  const amount = typeof node.properties.amount === 'number' ? money(node.properties.amount) : undefined
  const join = (...parts: (string | undefined)[]) => parts.filter(Boolean).join(' ')
  if (text('last4')) return join(text('product'), `··${text('last4')}`)
  if (text('heading')) return join(text('number'), text('heading'))
  if (text('sender')) return `${text('channel') ?? 'message'} from ${text('sender')}`
  const name = NAME_KEYS.map(text).find(Boolean)
  if (name) return join(name, text('version') && `v${text('version')}`, amount)
  const kind = KIND_KEYS.map(text).find(Boolean)
  if (kind) return join(amount, words(kind))
  if (text('product')) return `${text('product')} ${words(node.label).toLowerCase()}`
  return text('text') ?? node.id
}

/** A short name for a node or edge the run has loaded, and a hover title with its label and id. */
export function nameOf(graph: { nodes: Map<string, GraphNode>; edges: Map<string, GraphEdge> }, id: string) {
  const node = graph.nodes.get(id)
  if (node) return { text: caption(node), title: `${node.label} ${id}` }
  const edge = graph.edges.get(id)
  if (!edge) return { text: id, title: id }
  const end = (nodeId: string) => {
    const other = graph.nodes.get(nodeId)
    return other ? caption(other) : nodeId
  }
  return { text: words(edge.type).toLowerCase(), title: `${end(edge.src)} ${edge.type} ${end(edge.dst)} (${id})` }
}

export function fromNeighbor(
  centre: string,
  hit: { type: string; direction: 'out' | 'in'; edge: Record<string, unknown>; node: Record<string, unknown> },
): { node: GraphNode; edge: GraphEdge } {
  const { _label, id: nodeId, ...nodeProps } = hit.node as { _label: string; id: string }
  const { _type, id: edgeId, ...edgeProps } = hit.edge as { _type: string; id: string }
  return {
    node: { id: nodeId, label: _label, properties: nodeProps },
    edge: {
      id: edgeId,
      type: _type ?? hit.type,
      src: hit.direction === 'out' ? centre : nodeId,
      dst: hit.direction === 'out' ? nodeId : centre,
      properties: edgeProps,
    },
  }
}
