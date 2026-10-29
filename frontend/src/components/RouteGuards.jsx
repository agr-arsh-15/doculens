import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { Callout, Spinner } from './ui'

function Loading() {
  return (
    <div className="grid min-h-[50vh] place-items-center">
      <Spinner className="size-6" />
    </div>
  )
}

export function RequireAuth() {
  const auth = useAuth()
  const location = useLocation()
  if (auth.loading) return <Loading />
  if (!auth.signedIn) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  if (auth.meError?.status === 403) {
    return (
      <div className="mx-auto max-w-lg px-5 py-20">
        <Callout tone="error" title="Account suspended">{auth.meError.message}</Callout>
      </div>
    )
  }
  return <Outlet />
}

export function RequireAdmin() {
  const auth = useAuth()
  if (auth.loading) return <Loading />
  if (!auth.isAdmin) return <Navigate to="/" replace />
  return <Outlet />
}
