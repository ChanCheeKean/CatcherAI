import { createContext, useContext, useState, type ReactNode } from 'react'
import type { EventEnvelope } from '../api/types'

interface InspectorState {
  selected: EventEnvelope | null
  select: (event: EventEnvelope | null) => void
}

const InspectorContext = createContext<InspectorState | null>(null)

export function InspectorProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState<EventEnvelope | null>(null)
  return (
    <InspectorContext.Provider value={{ selected, select: setSelected }}>
      {children}
    </InspectorContext.Provider>
  )
}

export function useInspector(): InspectorState {
  const context = useContext(InspectorContext)
  if (!context) throw new Error('useInspector must be used within InspectorProvider')
  return context
}
