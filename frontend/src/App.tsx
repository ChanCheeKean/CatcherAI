import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { CasesPage } from './pages/CasesPage'
import { RunPage } from './pages/RunPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false, retry: 1 } },
})

const router = createBrowserRouter([
  { path: '/', element: <CasesPage /> },
  { path: '/cases/:caseId/runs/:runId', element: <RunPage /> },
])

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
