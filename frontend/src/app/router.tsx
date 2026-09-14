import { createBrowserRouter } from 'react-router-dom'
import { MissionControlPage } from '../features/mission-control/MissionControlPage'
import { RunObservatoryPage } from '../features/run-observatory/RunObservatoryPage'
import { Shell } from './Shell'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Shell />,
    children: [
      { index: true, element: <MissionControlPage /> },
      { path: 'runs/:runId', element: <RunObservatoryPage /> },
    ],
  },
])
