export interface CaseFilterState {
  q: string
  regime: string
  status: string
  stage: string
}

export const EMPTY_FILTERS: CaseFilterState = { q: '', regime: '', status: '', stage: '' }

const REGIMES = ['', 'reg_e', 'reg_z', 'network_only']
const STATUSES = ['', 'open', 'closed']
const STAGES = ['', 'intake', 'investigation', 'decision', 'resolution']

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-ink-faint">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-border bg-surface-1 px-2 py-1.5 text-sm text-ink focus-visible:outline-2 focus-visible:outline-cyan"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === '' ? 'Any' : option}
          </option>
        ))}
      </select>
    </label>
  )
}

export function CaseFilters({
  value,
  onChange,
}: {
  value: CaseFilterState
  onChange: (next: CaseFilterState) => void
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-1 min-w-[180px] flex-col gap-1 text-xs text-ink-faint">
        Search
        <input
          type="search"
          value={value.q}
          onChange={(event) => onChange({ ...value, q: event.target.value })}
          placeholder="Case ID, merchant, customer…"
          className="rounded-md border border-border bg-surface-1 px-2 py-1.5 text-sm text-ink placeholder:text-ink-faint focus-visible:outline-2 focus-visible:outline-cyan"
        />
      </label>
      <Select
        label="Regime"
        value={value.regime}
        options={REGIMES}
        onChange={(regime) => onChange({ ...value, regime })}
      />
      <Select
        label="Status"
        value={value.status}
        options={STATUSES}
        onChange={(status) => onChange({ ...value, status })}
      />
      <Select
        label="Stage"
        value={value.stage}
        options={STAGES}
        onChange={(stage) => onChange({ ...value, stage })}
      />
    </div>
  )
}
