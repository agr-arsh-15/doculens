import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode, lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import { RequireAdmin, RequireAuth } from './components/RouteGuards'
import { Spinner, TooltipProvider } from './components/ui'
import './index.css'
import { AuthProvider } from './lib/auth'
import Landing from './pages/Landing'

const Analyze = lazy(() => import('./pages/Analyze'))
const Report = lazy(() => import('./pages/Report'))
const Lab = lazy(() => import('./pages/Lab'))
const Compare = lazy(() => import('./pages/Compare'))
const HistoryPage = lazy(() => import('./pages/History'))
const Login = lazy(() => import('./pages/Login'))
const AuthCallback = lazy(() => import('./pages/AuthCallback'))
const Settings = lazy(() => import('./pages/Settings'))
const Admin = lazy(() => import('./pages/Admin'))
const Legal = lazy(() => import('./pages/Legal'))
const NotFound = lazy(() => import('./pages/NotFound'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => (err?.status === 0 || err?.status >= 500) && count < 2,
    },
  },
})

function PageFallback() {
  return (
    <div className="grid min-h-[50vh] place-items-center">
      <Spinner className="size-6" />
    </div>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <BrowserRouter>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route element={<AppShell />}>
                  <Route index element={<Landing />} />
                  <Route path="login" element={<Login />} />
                  <Route path="auth/callback" element={<AuthCallback />} />
                  <Route path="privacy" element={<Legal page="privacy" />} />
                  <Route path="terms" element={<Legal page="terms" />} />
                  <Route element={<RequireAuth />}>
                    <Route path="analyze/:docId" element={<Analyze />} />
                    <Route path="report/:id" element={<Report />} />
                    <Route path="lab/:id" element={<Lab />} />
                    <Route path="compare" element={<Compare />} />
                    <Route path="history" element={<HistoryPage />} />
                    <Route path="settings" element={<Settings />} />
                    <Route element={<RequireAdmin />}>
                      <Route path="admin" element={<Admin />} />
                    </Route>
                  </Route>
                  <Route path="*" element={<NotFound />} />
                </Route>
              </Routes>
            </Suspense>
          </BrowserRouter>
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
