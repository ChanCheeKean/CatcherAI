import type { GraphEdge, GraphNode } from '../api/types'

type IconName =
  | 'person' | 'wallet' | 'card' | 'key' | 'device' | 'globe' | 'phone' | 'mail' | 'house' | 'swap' | 'shield'
  | 'shop' | 'terminal' | 'tag' | 'box' | 'truck' | 'bot' | 'scroll' | 'flag' | 'doc' | 'question' | 'chat'
  | 'bolt' | 'note' | 'spark'

export type GraphRegion = 'identity' | 'commerce' | 'case'

export const GRAPH_REGIONS: { id: GraphRegion; title: string }[] = [
  { id: 'identity', title: 'Identity' },
  { id: 'commerce', title: 'Commerce' },
  { id: 'case', title: 'Case and knowledge' },
]

interface LabelStyle {
  region: GraphRegion
  color: string
  icon: IconName
}

const style = (region: GraphRegion, color: string, icon: IconName): LabelStyle => ({ region, color, icon })

/** Region, colour and icon per node label. Colours are grouped by region hue so families read at a glance. */
export const LABELS: Record<string, LabelStyle> = {
  Customer: style('identity', '#2f5fa8', 'person'),
  Account: style('identity', '#3a7ca5', 'wallet'),
  Card: style('identity', '#2e8b8b', 'card'),
  Token: style('identity', '#5b8fb9', 'key'),
  Device: style('identity', '#4c5f9a', 'device'),
  IP: style('identity', '#5a7d9a', 'globe'),
  Phone: style('identity', '#3d6e91', 'phone'),
  Email: style('identity', '#6f8fc4', 'mail'),
  Address: style('identity', '#28707a', 'house'),
  MerchantAccount: style('identity', '#46609a', 'shield'),
  Transaction: style('commerce', '#b4651f', 'swap'),
  Authorization: style('commerce', '#c48a2c', 'shield'),
  Merchant: style('commerce', '#8a6d1f', 'shop'),
  Terminal: style('commerce', '#a4762f', 'terminal'),
  Descriptor: style('commerce', '#a3703f', 'tag'),
  PurchaseOrder: style('commerce', '#c0692f', 'box'),
  Shipment: style('commerce', '#9c7a3c', 'truck'),
  AgentProvider: style('commerce', '#7a5c2e', 'bot'),
  Mandate: style('commerce', '#a5502b', 'scroll'),
  Dispute: style('case', '#a83a4e', 'flag'),
  EvidenceItem: style('case', '#8b4a5f', 'doc'),
  EvidenceRequest: style('case', '#b0603d', 'question'),
  Communication: style('case', '#8b5a3c', 'chat'),
  AccountEvent: style('case', '#9a4a6a', 'bolt'),
  MemoryNote: style('case', '#5c7a4a', 'note'),
  Finding: style('case', '#1c7a57', 'spark'),
}

const FALLBACK: LabelStyle = style('case', '#4f5c70', 'doc')
export const labelStyle = (label: string): LabelStyle => LABELS[label] ?? FALLBACK

const CAPTION_KEYS = ['name', 'text', 'street', 'number', 'address', 'handle', 'wallet', 'last4', 'kind']

/** The most readable property of a node, for the caption under it; falls back to the id. */
export function caption(node: GraphNode): string {
  const key = CAPTION_KEYS.find((k) => typeof node.properties[k] === 'string' && node.properties[k])
  const value = key ? String(node.properties[key]) : node.id
  return value.length > 22 ? `${value.slice(0, 21)}…` : value
}

/** Nodes and edges written by an agent carry the id of the run that wrote them. */
export const isAgentWritten = (item: GraphNode | GraphEdge) =>
  'label' in item ? item.label === 'Finding' || item.label === 'MemoryNote' : Boolean(item.properties.run_id)

/** Compact neighbour dicts from `/graph/neighbors` become the same shapes as `/graph/nodes`. */
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
