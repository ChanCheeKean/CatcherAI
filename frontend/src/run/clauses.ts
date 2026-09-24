import type { CaseReport } from '../api/types'

/** System Improvements that change a policy; the Clauses behind one are the ones the report weighs against each other. */
const POLICY_TARGETS = new Set(['amex_policy', 'merchant_policy'])

/** The report's policy-basis Clauses that a policy System Improvement cites, in order of first mention. */
export function comparedClauses(report: CaseReport): string[] {
  const basis = new Set(report.policy_basis.map((citation) => citation.document_id))
  const cited = report.system_improvements
    .filter((item) => POLICY_TARGETS.has(item.target))
    .flatMap((item) => item.evidence.flatMap((link) => link.node_ids))
  return [...new Set(cited.filter((id) => basis.has(id)))]
}

/** Everything the report says while citing `id`: claims, their excerpts, and why it is policy basis. */
export function textsCiting(report: CaseReport, id: string): string[] {
  const links = [...report.charges, ...report.hypotheses, ...report.system_improvements].flatMap((item) => item.evidence)
  return [
    ...links.filter((link) => link.node_ids.includes(id)).flatMap((link) => [link.claim, link.source_excerpt ?? '']),
    ...report.policy_basis.filter((citation) => citation.document_id === id).map((citation) => citation.why),
  ].filter(Boolean)
}

/** Split at end punctuation followed by a space, so "Terms 4.3" stays one sentence. */
const sentences = (text: string) => text.split(/(?<=[.!?])\s+/).filter(Boolean)
const normal = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
const contentWords = (text: string) => new Set(normal(text).split(' ').filter((word) => word.length > 3))

/**
 * The sentence of a Clause that the report leans on: one it quotes word for word, otherwise the one
 * sharing the most words with what cites the Clause.
 */
export function decidingSentence(text: string, citing: string[]): string {
  const said = citing.map(normal)
  const heard = new Set(citing.flatMap((line) => [...contentWords(line)]))
  const score = (sentence: string) =>
    (said.some((line) => line.includes(normal(sentence))) ? 1000 : 0) + [...contentWords(sentence)].filter((word) => heard.has(word)).length
  return sentences(text).reduce((best, sentence) => (score(sentence) > score(best) ? sentence : best), sentences(text)[0] ?? '')
}
