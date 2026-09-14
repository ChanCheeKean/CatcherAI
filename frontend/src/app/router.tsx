import { createBrowserRouter } from 'react-router-dom'
import { MissionControlPage } from '../features/mission-control/MissionControlPage'
import { Shell } from './Shell'
import { MemoryExplorerPage } from '../features/memory/MemoryExplorerPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    children: [
      { index: true, element: <MissionControlPage /> },
      { path: 'runs/:runId', lazy: async () => ({ Component: (await import('../features/run-observatory/RunObservatoryPage')).RunObservatoryPage }) },
      { path: 'memory', element: <MemoryExplorerPage /> },
      { path: 'graph', lazy: async () => ({ Component: (await import('../features/graph/GraphLabPage')).GraphLabPage }) },
      { path: 'evaluation', lazy: async () => ({ Component: (await import('../features/evaluation/EvaluationPage')).EvaluationPage }) },
    ],
  },
])
