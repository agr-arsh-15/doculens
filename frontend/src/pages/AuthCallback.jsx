import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Callout, Spinner } from '../components/ui'
import { safeNext, supabase, useAuth } from '../lib/auth'

export default function AuthCallback() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const providerError = params.get('error_description') || params.get('error')
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    if (auth.signedIn) navigate(next, { replace: true })
  }, [auth.signedIn, navigate, next])

  useEffect(() => {
    const t = setTimeout(() => setTimedOut(true), 10_000)
    return () => clearTimeout(t)
  }, [])

  // The PKCE code in the URL is exchanged by supabase-js on load; if that already failed, try once more.
  useEffect(() => {
    const code = params.get('code')
    if (!supabase || !code) return
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) supabase.auth.exchangeCodeForSession(code).catch(() => {})
    })
  }, [params])

  if (providerError || timedOut) {
    return (
      <div className="mx-auto max-w-md px-5 py-20">
        <Callout tone="error" title="Sign-in did not complete">
          {providerError || 'The sign-in link expired or was already used.'}{' '}
          <Link to={`/login?next=${encodeURIComponent(next)}`} className="font-medium underline">Try again</Link>
        </Callout>
      </div>
    )
  }
  return (
    <div className="grid min-h-[50vh] place-items-center">
      <div className="flex items-center gap-3 text-sm text-muted">
        <Spinner className="size-5" /> Signing you in...
      </div>
    </div>
  )
}
