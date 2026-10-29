import { LockKeyhole, ScanLine } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { Button, Callout, Card, Chip } from '../components/ui'
import { safeNext, useAuth } from '../lib/auth'

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-5" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  )
}

export default function Login() {
  const auth = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const [email, setEmail] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (auth.signedIn && !auth.loading) return <Navigate to={next} replace />

  const google = async () => {
    setBusy(true)
    setError(null)
    const { error: err } = await auth.signInWithGoogle(next)
    if (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="paper-grain grid min-h-[calc(100vh-8.5rem)] place-items-center px-5 py-12">
      <Card className="w-full max-w-md p-8">
        <Chip className="mb-5" icon={ScanLine}>Document X-Ray</Chip>
        <h1 className="font-serif text-3xl font-bold tracking-tight">Sign in to DocuLens</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Your documents and reports are private to your account. Sign in to upload a document and see its risk report.
        </p>

        {auth.mode === 'test' ? (
          <form
            className="mt-7 space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (email.includes('@')) auth.signInForTests(email)
            }}
          >
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              data-testid="test-email"
              className="h-11 w-full rounded-lg border border-line bg-surface-2 px-3 text-sm outline-none focus:border-accent"
            />
            <Button type="submit" variant="primary" className="w-full" data-testid="test-sign-in">
              Sign in (test mode)
            </Button>
          </form>
        ) : (
          <Button onClick={google} loading={busy} className="mt-7 h-11 w-full justify-center gap-3 text-[15px]" data-testid="google-sign-in">
            {!busy && <GoogleMark />}
            Continue with Google
          </Button>
        )}

        {error && (
          <Callout tone="error" className="mt-4" title="Sign-in failed">
            {error}
          </Callout>
        )}

        <div className="mt-6 flex items-start gap-2 rounded-lg bg-sunken/60 p-3 text-xs leading-relaxed text-muted">
          <LockKeyhole className="mt-0.5 size-3.5 shrink-0" />
          <span>
            We only receive your name, e-mail address and profile picture from Google. By continuing you agree to the{' '}
            <Link to="/terms" className="underline underline-offset-2 hover:text-ink">Terms</Link> and{' '}
            <Link to="/privacy" className="underline underline-offset-2 hover:text-ink">Privacy Policy</Link>.
          </span>
        </div>
      </Card>
    </div>
  )
}
