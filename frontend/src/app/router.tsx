import { createBrowserRouter } from 'react-router-dom'
import { MissionControlPage } from '../features/mission-control/MissionControlPage'
import { RunObservatoryPage } from '../features/run-observatory/RunObservatoryPage'
import { Shell } from './Shell'
import { MemoryExplorerPage } from '../features/memory/MemoryExplorerPage'
import { GraphLabPage } from '../features/graph/GraphLabPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    children: [
      { index: true, element: <MissionControlPage /> },
      { path: 'runs/:runId', element: <RunObservatoryPage /> },
      { path: 'memory', element: <MemoryExplorerPage /> },
      { path: 'graph', element: <GraphLabPage /> },
    ],
  },
])
