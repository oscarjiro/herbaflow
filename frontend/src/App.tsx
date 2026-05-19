import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { queryClient } from '@/lib/queryClient'
import Layout from '@/components/layout/Layout'
import LandingPage from '@/pages/LandingPage'
import SetupPage from '@/pages/SetupPage'
import PipelinePage from '@/pages/PipelinePage'
import AboutPage from '@/pages/AboutPage'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<LandingPage />} />
            <Route path="analysis" element={<SetupPage />} />
            <Route path="analysis/:id" element={<PipelinePage />} />
            <Route path="about" element={<AboutPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
