import { useMutation, useQueryClient } from '@tanstack/react-query'
import { KeyRound, ShieldAlert, Sparkles, Trash2, UserRound } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Callout, Card, Meter } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'

function Section({ icon: Icon, title, description, children }) {
  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-sunken text-ink-2">
          <Icon className="size-[18px]" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
          <div className="mt-4">{children}</div>
        </div>
      </div>
    </Card>
  )
}

function UsageRow({ label, used, limit, unlimited }) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-sm">
        <span>{label}</span>
        <span className="font-mono text-xs text-muted">{unlimited ? `${used} used · no limit (your key)` : `${used} of ${limit}`}</span>
      </div>
      <Meter value={unlimited ? 0 : Math.min(used, limit)} max={Math.max(limit, 1)} tone={!unlimited && used >= limit ? 'critical' : 'ok'} />
    </div>
  )
}

export default function Settings() {
  const auth = useAuth()
  const user = auth.user
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [key, setKey] = useState('')
  const [confirm, setConfirm] = useState('')

  const refreshMe = (me) => queryClient.setQueryData(['me'], me)
  const saveKey = useMutation({ mutationFn: () => api.setLlmKey(key.trim()), onSuccess: (me) => { refreshMe(me); setKey('') } })
  const removeKey = useMutation({ mutationFn: api.deleteLlmKey, onSuccess: refreshMe })
  const deleteAccount = useMutation({
    mutationFn: api.deleteAccount,
    onSuccess: async () => {
      await auth.signOut()
      navigate('/', { replace: true })
    },
  })

  if (!user) return null
  const u = user.usage
  return (
    <div className="mx-auto max-w-3xl space-y-5 px-5 py-10">
      <div>
        <h1 className="font-serif text-3xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted">Your account, AI usage and data.</p>
      </div>

      <Section icon={UserRound} title="Profile">
        <div className="flex items-center gap-4">
          {user.avatar_url ? (
            <img src={user.avatar_url} alt="" referrerPolicy="no-referrer" className="size-12 rounded-full border border-line object-cover" />
          ) : (
            <div className="grid size-12 place-items-center rounded-full bg-sunken font-semibold">{(user.name || user.email)[0].toUpperCase()}</div>
          )}
          <div className="min-w-0">
            <div className="font-medium">{user.name || 'No name on the account'}</div>
            <div className="truncate text-sm text-muted">{user.email}</div>
            <div className="mt-0.5 text-xs text-faint">
              {user.role === 'admin' ? 'Administrator · ' : ''}Member since {new Date(user.created_at).toLocaleDateString()}
            </div>
          </div>
        </div>
      </Section>

      <Section icon={Sparkles} title="AI usage today" description="AI analyses and answers on the DocuLens key reset at midnight UTC. Beyond the limit, documents are still checked by the built-in rules.">
        {!u.ai_enabled && !user.has_own_key && (
          <Callout tone="warning" className="mb-4">AI is paused by the administrator. Add your own Groq key below to keep using it.</Callout>
        )}
        <div className="space-y-4" data-testid="usage">
          <UsageRow label="AI analyses" used={u.ai_analyses_used} limit={u.ai_analyses_limit} unlimited={user.has_own_key} />
          <UsageRow label="AI answers in “Ask the document”" used={u.chat_messages_used} limit={u.chat_messages_limit} unlimited={user.has_own_key} />
        </div>
      </Section>

      <Section
        icon={KeyRound}
        title="Your own Groq API key (optional)"
        description="Use your own free Groq key for unlimited AI analyses. It is checked with Groq, stored encrypted, and used only for your requests."
      >
        {user.has_own_key ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface-2 px-4 py-3">
            <div className="text-sm">
              Key saved: <span className="font-mono">{user.own_key_hint}</span>
            </div>
            <Button size="sm" variant="danger" loading={removeKey.isPending} onClick={() => removeKey.mutate()} data-testid="remove-key">Remove key</Button>
          </div>
        ) : (
          <form
            className="flex flex-col gap-2 sm:flex-row"
            onSubmit={(e) => {
              e.preventDefault()
              saveKey.mutate()
            }}
          >
            <input
              type="password"
              autoComplete="off"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="gsk_..."
              className="h-10 flex-1 rounded-lg border border-line bg-surface-2 px-3 font-mono text-sm outline-none focus:border-accent"
              data-testid="key-input"
            />
            <Button type="submit" variant="primary" loading={saveKey.isPending} disabled={key.trim().length < 20}>Check and save</Button>
          </form>
        )}
        {(saveKey.error || removeKey.error) && (
          <Callout tone="error" className="mt-3">{(saveKey.error || removeKey.error).message}</Callout>
        )}
        <p className="mt-3 text-xs text-muted">
          Get a free key at{' '}
          <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-ink">console.groq.com/keys</a>.
        </p>
      </Section>

      {auth.mode !== 'local' && (
        <Section icon={ShieldAlert} title="Delete account" description="Permanently deletes your account, every document and report, your stored files and your saved key. This cannot be undone.">
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Type DELETE to confirm"
              className="h-10 flex-1 rounded-lg border border-line bg-surface-2 px-3 text-sm outline-none focus:border-critical"
              data-testid="delete-confirm"
            />
            <Button variant="danger" icon={Trash2} disabled={confirm !== 'DELETE'} loading={deleteAccount.isPending} onClick={() => deleteAccount.mutate()} data-testid="delete-account">
              Delete my account
            </Button>
          </div>
          {deleteAccount.error && <Callout tone="error" className="mt-3">{deleteAccount.error.message}</Callout>}
        </Section>
      )}
    </div>
  )
}
