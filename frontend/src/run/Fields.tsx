import { Fragment } from 'react'
import { words } from './format'

const ID = /^[A-Z]{1,4}-[\w-]+$/
/** Graph ids inside prose: a known prefix and at least one digit, so "IP-based" and "T-Mobile" stay words. */
const REF_IN_TEXT =
  /((?:CUS|ACC|CRD|DEV|IP|PHN|EML|ADR|MER|TRM|DSC|AUT|TXN|ORD|SHP|TOK|AGP|MDT|DSP|EVI|ERQ|COM|AEV|MEM|FND|MAC|E)-(?=[A-Za-z0-9-]*\d)[A-Za-z0-9][A-Za-z0-9-]*)/

/** A graph id as a small monospace chip. */
export function Ref({ id }: { id: string }) {
  return <span className="ref">{id}</span>
}

/** Prose with every graph id it mentions turned into a chip, so ids stand out from the sentence. */
export function Prose({ children }: { children: string }) {
  return (
    <>
      {children.split(REF_IN_TEXT).map((part, index) =>
        index % 2 ? <Ref key={index} id={part} /> : <Fragment key={index}>{part}</Fragment>,
      )}
    </>
  )
}

/** Chips for a list of ids, keeping the first few and folding the rest behind a count. */
export function Refs({ ids, max = 6 }: { ids: string[]; max?: number }) {
  if (!ids.length) return null
  const shown = ids.slice(0, max)
  const rest = ids.slice(max)
  return (
    <span className="flex flex-wrap items-center gap-1">
      {shown.map((id) => (
        <Ref key={id} id={id} />
      ))}
      {rest.length > 0 && (
        <details className="contents">
          <summary className="ref cursor-pointer text-graphite">+{rest.length} more</summary>
          {rest.map((id) => (
            <Ref key={id} id={id} />
          ))}
        </details>
      )}
    </span>
  )
}

/** Any structured value as readable fields: labelled rows, bullet lists, and ids as chips. */
export function Fields({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'string')
    return ID.test(value) ? <Ref id={value} /> : <Prose>{value}</Prose>
  if (typeof value !== 'object') return <span className="tabular-nums">{String(value)}</span>
  if (Array.isArray(value)) {
    if (!value.length) return null
    if (value.every((item) => typeof item === 'string' && ID.test(item)))
      return (
        <span className="flex flex-wrap gap-1">
          {value.map((id) => (
            <Ref key={id} id={id} />
          ))}
        </span>
      )
    return (
      <ul className="list-disc space-y-1.5 pl-4 marker:text-graphite/60">
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
    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-2">
      {entries.map(([key, v]) => (
        <Fragment key={key}>
          <dt className="pt-px text-xs font-medium text-graphite">{words(key)}</dt>
          <dd className="min-w-0 break-words">
            <Fields value={v} />
          </dd>
        </Fragment>
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
