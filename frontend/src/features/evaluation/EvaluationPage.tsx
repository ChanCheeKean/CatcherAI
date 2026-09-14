import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { EvaluationProvingEvent } from '../../api/types'

function percent(value: number) { return `${Math.round(value * 100)}%` }

export function EvaluationPage() {
  const [params, setParams] = useSearchParams()
  const reports = useQuery({ queryKey: ['evaluation-reports'], queryFn: api.listEvaluationReports })
  const reportId = params.get('report') ?? reports.data?.[0]?.report_id ?? null
  const report = useQuery({ queryKey: ['evaluation-report', reportId], queryFn: () => api.getEvaluationReport(reportId!), enabled: Boolean(reportId) })

  useEffect(() => {
    if (!params.get('report') && reportId) setParams({ report: reportId }, { replace: true })
  }, [params, reportId, setParams])

  const selected = report.data?.proving_events.find((event) =>
    event.capability === params.get('capability') && event.case_id === params.get('case') &&
    (!params.get('run') || event.run_id === params.get('run')) &&
    (!params.get('seq') || event.seq === Number(params.get('seq'))),
  )

  function prove(capability: string, caseId: string) {
    const event = report.data?.proving_events.find((item) => item.capability === capability && item.case_id === caseId)
    if (!event || !reportId) return
    setParams({ report: reportId, capability, case: caseId, run: event.run_id, seq: String(event.seq) })
  }

  if (reports.isLoading) return <p className="p-6 text-sm text-ink-faint">Loading evaluation reports…</p>
  if (!reports.data?.length) return <p className="p-6 text-sm text-ink-faint">No durable evaluation reports found.</p>

  const matrix = report.data?.capability_matrix ?? {}
  const cases = [...new Set(Object.values(matrix).flatMap((row) => Object.keys(row)))].sort()
  const summary = report.data?.summary

  return <div className="min-h-full p-4 sm:p-6">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="font-mono text-xs uppercase tracking-widest text-violet">Evaluation coverage</p><h1 className="mt-1 text-2xl font-bold text-ink">Capability matrix</h1><p className="mt-1 text-sm text-ink-muted">Every marked cell resolves to a recorded proving event.</p></div>
      <select aria-label="Evaluation report" value={reportId ?? ''} onChange={(event) => setParams({ report: event.target.value })} className="rounded-md border border-border bg-surface-1 px-3 py-2 font-mono text-xs text-ink">
        {reports.data.map((item) => <option key={item.report_id} value={item.report_id}>{item.report_id}</option>)}
      </select>
    </header>
    {summary && <section className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {[['Pass rate', percent(summary.pass_rate)], ['Attempts', `${summary.passed}/${summary.attempts}`], ['Stable', `${summary.stable_cases}/${summary.cases}`], ['Reconciled', `${summary.reconciled_attempts}/${summary.attempts}`]].map(([label, value]) => <div key={label} className="rounded-lg border border-border bg-surface-1 p-3"><p className="text-xs text-ink-faint">{label}</p><p className="mt-1 font-mono text-lg text-emerald">{value}</p></div>)}
    </section>}
    {report.isLoading && <p className="mt-6 text-sm text-ink-faint">Reading report…</p>}
    {report.data && <div className="mt-5 overflow-auto rounded-lg border border-border bg-surface-1">
      <table className="min-w-max border-collapse text-xs"><thead><tr className="sticky top-0 bg-surface-2"><th className="sticky left-0 z-10 bg-surface-2 px-3 py-2 text-left text-ink-muted">Capability</th>{cases.map((caseId) => <th key={caseId} className="px-2 py-2 font-mono font-normal text-ink-faint">{caseId.replace('DSP-2026-', '')}</th>)}</tr></thead>
      <tbody>{Object.entries(matrix).sort().map(([capability, row]) => <tr key={capability} className="border-t border-border"><th className="sticky left-0 bg-surface-1 px-3 py-2 text-left font-medium text-ink">{capability.replaceAll('_', ' ')}</th>{cases.map((caseId) => { const covered = row[caseId]; return <td key={caseId} className="p-1 text-center">{covered === undefined ? <span className="text-ink-faint">·</span> : <button type="button" aria-label={`${capability} ${caseId} proving event`} onClick={() => prove(capability, caseId)} className={`size-7 rounded border font-mono ${covered ? 'border-emerald/30 bg-emerald/10 text-emerald hover:bg-emerald/20' : 'border-rose/30 bg-rose/10 text-rose'}`}>{covered ? '✓' : '×'}</button>}</td>})}</tr>)}</tbody></table>
    </div>}
    <ProvingEvent event={selected} />
  </div>
}

function ProvingEvent({ event }: { event?: EvaluationProvingEvent }) {
  if (!event) return <p className="mt-4 rounded-lg border border-dashed border-border p-4 text-sm text-ink-faint">Select a capability cell to inspect its first recorded proof.</p>
  return <section id="proving-event" className="mt-4 rounded-lg border border-cyan/30 bg-cyan/5 p-4"><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs text-cyan">seq {event.seq}</span><span className="font-mono text-xs text-violet">{event.type}</span><span className="text-xs text-ink-faint">{event.case_id} · attempt {event.run_id.slice(-8)}</span></div><p className="mt-2 text-sm text-ink">{event.summary}</p><p className="mt-2 font-mono text-xs text-ink-faint">virtual {event.ts_virtual}</p></section>
}
