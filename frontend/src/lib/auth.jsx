import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createClient } from '@supabase/supabase-js'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, configureAuth } from './api'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
// The publishable key (sb_publishable_...) is safe to ship to browsers; legacy projects use the anon key.
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY
// supabase: Google sign-in (hosted). local: no accounts (laptop). test: e-mail only, for automated tests.
export const AUTH_MODE = import.meta.env.VITE_AUTH_MODE || (SUPABASE_URL ? 'supabase' : 'local')
const TEST_KEY = 'doculens.testSession'

export const supabase =
  AUTH_MODE === 'supabase'
    ? createClient(SUPABASE_URL, SUPABASE_KEY, {
        auth: { flowType: 'pkce', persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
      })
    : null

let handleUnauthorized = () => {}
configureAuth({
  getToken: async () => {
    if (supabase) return (await supabase.auth.getSession()).data.session?.access_token ?? null
    if (AUTH_MODE === 'test') return readTestSession()?.access_token ?? null
    return null
  },
  unauthorized: () => handleUnauthorized(),
})

const AuthContext = createContext(null)

function readTestSession() {
  try {
    return JSON.parse(localStorage.getItem(TEST_KEY))
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState(() =>
    AUTH_MODE === 'local' ? { local: true } : AUTH_MODE === 'test' ? readTestSession() : undefined,
  )

  useEffect(() => {
    if (!supabase) return undefined
    supabase.auth.getSession().then(({ data }) => setSession(data.session ?? null))
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next ?? null))
    return () => data.subscription.unsubscribe()
  }, [])

  const signOut = useCallback(async () => {
    if (supabase) await supabase.auth.signOut()
    if (AUTH_MODE === 'test') localStorage.removeItem(TEST_KEY)
    if (AUTH_MODE !== 'local') setSession(null)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    handleUnauthorized = () => {
      if (AUTH_MODE !== 'local') signOut()
    }
  }, [signOut])

  const signedIn = !!session
  const me = useQuery({ queryKey: ['me'], queryFn: api.me, enabled: signedIn, staleTime: 30_000, retry: 1 })

  const value = useMemo(
    () => ({
      mode: AUTH_MODE,
      loading: session === undefined || (signedIn && me.isLoading),
      signedIn,
      user: me.data ?? null,
      meError: me.error,
      isAdmin: me.data?.role === 'admin',
      signInWithGoogle: (next = '/') =>
        supabase.auth.signInWithOAuth({
          provider: 'google',
          options: { redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}` },
        }),
      signInForTests: (email) => {
        const next = { access_token: `test-${email.trim().toLowerCase()}` }
        localStorage.setItem(TEST_KEY, JSON.stringify(next))
        setSession(next)
      },
      signOut,
    }),
    [session, signedIn, me.data, me.isLoading, me.error, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}

/** Only allow same-site relative paths as a post-login destination. */
export function safeNext(value) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : '/'
}
