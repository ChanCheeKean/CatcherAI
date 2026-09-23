import type { GraphEdge, GraphNode, GraphOntology } from '../api/types'

export type GraphRegion = string
export type IconName = 'person' | 'swap' | 'scroll' | 'flag'
export interface LabelStyle { region: GraphRegion; color: string; icon: IconName }

const PALETTE: Record<string, string[]> = {
  parties: ['#2f5fa8', '#3a7ca5', '#2e8b8b', '#5b8fb9', '#4c5f9a', '#5a7d9a', '#3d6e91', '#6f8fc4', '#28707a', '#46609a', '#4073ab', '#526fa0'],
  commerce: ['#b4651f', '#c48a2c', '#8a6d1f', '#a4762f', '#a3703f', '#c0692f', '#9c7a3c', '#7a5c2e', '#a5502b', '#bd7b29', '#946a34', '#a87926'],
  terms: ['#35785c', '#448c64', '#527f3e', '#298570', '#5d9154', '#39725c', '#67843d', '#407b62', '#5a926e', '#387e55', '#738b43', '#4e8069'],
  case: ['#a83a4e', '#8b4a5f', '#b0605b', '#9a4a6a', '#ad586c', '#8e3c51', '#b47580', '#9c5060', '#a35d75', '#8f5968', '#b04d62', '#995666'],
}
const ICONS: Record<string, IconName> = { parties: 'person', commerce: 'swap', terms: 'scroll', case: 'flag' }
const FALLBACK_COLOR = '#4f5c70'

export function graphModel(ontology: GraphOntology) {
  const regions = Object.entries(ontology.groups).map(([id, group]) => ({ id, title: group.title }))
  const positions = new Map<string, number>()
  const styles = new Map<string, LabelStyle>()
  for (const [label, { group }] of Object.entries(ontology.labels)) {
    const index = positions.get(group) ?? 0
    positions.set(group, index + 1)
    const palette = PALETTE[group] ?? [FALLBACK_COLOR]
    styles.set(label, { region: group, color: palette[index % palette.length], icon: ICONS[group] ?? 'flag' })
  }
  const last = regions.at(-1)?.id ?? 'case'
  const fallback: LabelStyle = { region: last, color: FALLBACK_COLOR, icon: ICONS[last] ?? 'flag' }
  return { regions, labelStyle: (label: string) => styles.get(label) ?? fallback }
}

const CAPTION_KEYS = ['name', 'text', 'title', 'summary', 'number', 'last4', 'kind']

export function caption(node: GraphNode): string {
  const key = CAPTION_KEYS.find((k) => typeof node.properties[k] === 'string' && node.properties[k])
  const value = key ? String(node.properties[key]) : node.id
  return value.length > 22 ? `${value.slice(0, 21)}…` : value
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
