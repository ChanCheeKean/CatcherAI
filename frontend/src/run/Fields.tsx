import { words } from './format'

const ID = /^[A-Z]{1,4}-[\w-]+$/

/** Any structured value as readable fields: labelled rows, bullet lists, and ids as chips. */
export function Fields({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'string')
    return ID.test(value) ? <span className="id-chip rounded-sm border bg-vellum px-1">{value}</span> : <span>{value}</span>
  if (typeof value !== 'object') return <span className="tabular-nums">{String(value)}</span>
  if (Array.isArray(value)) {
    if (!value.length) return null
    if (value.every((item) => typeof item === 'string' && ID.test(item)))
      return (
        <span className="flex flex-wrap gap-1">
          {value.map((id) => (
            <Fields key={id} value={id} />
          ))}
        </span>
      )
    return (
      <ul className="list-disc space-y-1 pl-4">
        {value.map((item, index) => (
          <li key={index}>
            <Fields value={item} />
          </li>
        ))}
      </ul>
    )
  }
  const entries = Object.entries(value).filter(([, v]) => v !== null && v !== '' && !(Array.isArray(v) && !v.length))
  return (
    <dl className="space-y-1.5">
      {entries.map(([key, v]) => (
        <div key={key}>
          <dt className="text-xs font-medium text-graphite">{words(key)}</dt>
          <dd className="break-words">
            <Fields value={v} />
          </dd>
        </div>
      ))}
    </dl>
  )
}

/** The exact JSON, scrollable, for copying into a bug report. */
export function Json({ value, max = 'max-h-72' }: { value: unknown; max?: string }) {
  return (
    <pre className={`id-chip ${max} overflow-auto rounded-sm border bg-paper p-2 whitespace-pre-wrap`}>
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}
