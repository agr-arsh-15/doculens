import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity, AlertTriangle, Ban, CheckCircle2, ChevronLeft, ChevronRight, Cpu, FileText, HardDrive, KeyRound, Search,
  Sparkles, UserPlus, Users,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip as ChartTooltip,
  XAxis, YAxis,
} from 'recharts'
import { Button, Callout, Card, Chip, cx, Spinner, Switch } from '../components/ui'
import { api } from '../lib/api'

const CHART = { ink: 'var(--ink)', ai: 'var(--ok)', signups: 'var(--high)', grid: 'var(--line)', muted: 'var(--muted)' }
const PIE = ['var(--ok)', 'var(--ink-2)', 'var(--caution)', 'var(--high)', 'var(--critical)', 'var(--info)', 'var(--faint)', 'var(--line-strong)']

const bytes = (n) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`)
const ago = (iso) => {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 2) return 'just now'
  if (mins < 60) return `${mins} min ago`
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`
  return `${Math.round(mins / 1440)} d ago`
}

function Kpi({ icon: Icon, label, value, hint, tone }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-muted">
        <Icon className={cx('size-4', tone)} /> {label}
      </div>
      <div className="mt-2 font-serif text-3xl font-bold tracking-tight" data-testid={`kpi-${label}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </Card>
  )
}

function ChartCard({ title, children, className }) {
  return (
    <Card className={cx('p-5', className)}>
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {children}
    </Card>
  )
}

const tooltipStyle = { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10, fontSize: 12 }

function Mix({ data, empty }) {
  const rows = Object.entries(data).map(([name, value]) => ({ name, value }))
  if (!rows.length) return <div className="grid h-48 place-items-center text-sm text-muted">{empty}</div>
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid horizontal={false} stroke={CHART.grid} />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: CHART.muted }} />
        <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11, fill: CHART.muted }} />
        <ChartTooltip contentStyle={tooltipStyle} cursor={{ fill: 'var(--sunken)' }} />
        <Bar dataKey="value" fill={CHART.ink} radius={[0, 4, 4, 0]} name="Analyses" maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function UserRow({ user, onSave, saving }) {
  const [limit, setLimit] = useState(String(user.ai_daily_limit))
  const dirty = limit !== String(user.ai_daily_limit) && limit !== ''
  const blocked = user.status === 'blocked'
  return (
    <tr className={cx('border-t border-line', blocked && 'opacity-60')} data-testid="admin-user-row">
      <td className="py-2.5 pr-3">
        <div className="font-medium">{user.name || user.email.split('@')[0]}</div>
        <div className="text-xs text-muted">{user.email}</div>
      </td>
      <td className="py-2.5 pr-3 text-xs text-muted">
        <div>Joined {new Date(user.created_at).toLocaleDateString()}</div>
        <div>Active {ago(user.last_seen_at)}</div>
      </td>
      <td className="py-2.5 pr-3 text-center font-mono text-xs">{user.analyses}</td>
      <td className="py-2.5 pr-3">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-xs text-muted">{user.ai_used_today} /</span>
          <input
            type="number"
            min={0}
            max={1000}
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            className="h-8 w-16 rounded-md border border-line bg-surface-2 px-2 text-xs outline-none focus:border-accent"
            aria-label={`Daily AI limit for ${user.email}`}
          />
          {dirty && <Button size="sm" variant="primary" loading={saving} onClick={() => onSave({ ai_daily_limit: Number(limit) })}>Save</Button>}
          {!dirty && user.limit_overridden && (
            <button className="cursor-pointer text-[11px] text-muted underline underline-offset-2 hover:text-ink" onClick={() => onSave({ reset_limit: true })}>
              reset
            </button>
          )}
        </div>
        {user.has_own_key && <div className="mt-1 inline-flex items-center gap-1 text-[11px] text-ok"><KeyRound className="size-3" /> own key</div>}
      </td>
      <td className="py-2.5 text-right">
        {user.role === 'admin' ? (
          <Chip className="text-[11px]">Admin</Chip>
        ) : (
          <Button
            size="sm"
            variant={blocked ? 'secondary' : 'danger'}
            icon={blocked ? CheckCircle2 : Ban}
            loading={saving}
            onClick={() => onSave({ status: blocked ? 'active' : 'blocked' })}
            data-testid="toggle-block"
          >
            {blocked ? 'Unblock' : 'Block'}
          </Button>
        )}
      </td>
    </tr>
  )
}

function UsersTable() {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(q)
      setOffset(0)
    }, 300)
    return () => clearTimeout(t)
  }, [q])
  const users = useQuery({ queryKey: ['admin-users', search, offset], queryFn: () => api.admin.users(search, offset), placeholderData: keepPreviousData })
  const update = useMutation({
    mutationFn: ({ id, patch }) => api.admin.updateUser(id, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-kpis'] })
    },
  })
  const page = users.data
  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">Users {page && <span className="font-normal text-muted">({page.total})</span>}</h3>
        <label className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-faint" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by e-mail or name"
            className="h-9 w-64 rounded-lg border border-line bg-surface-2 pl-8 pr-3 text-sm outline-none focus:border-accent"
          />
        </label>
      </div>
      {update.error && <Callout tone="error" className="mb-3">{update.error.message}</Callout>}
      {!page ? (
        <div className="grid h-32 place-items-center"><Spinner /></div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-faint">
                <th className="pb-2 pr-3 font-semibold">User</th>
                <th className="pb-2 pr-3 font-semibold">Activity</th>
                <th className="pb-2 pr-3 text-center font-semibold">Analyses</th>
                <th className="pb-2 pr-3 font-semibold">AI today / daily limit</th>
                <th className="pb-2 text-right font-semibold">Access</th>
              </tr>
            </thead>
            <tbody>
              {page.users.map((u) => (
                <UserRow key={`${u.id}-${u.ai_daily_limit}`} user={u} saving={update.isPending && update.variables?.id === u.id} onSave={(patch) => update.mutate({ id: u.id, patch })} />
              ))}
            </tbody>
          </table>
          {page.users.length === 0 && <div className="py-8 text-center text-sm text-muted">No users match.</div>}
        </div>
      )}
      {page && page.total > 25 && (
        <div className="mt-3 flex items-center justify-end gap-2 text-xs text-muted">
          {offset + 1}-{Math.min(offset + 25, page.total)} of {page.total}
          <Button size="sm" variant="ghost" icon={ChevronLeft} disabled={offset === 0} onClick={() => setOffset(offset - 25)} aria-label="Previous page" />
          <Button size="sm" variant="ghost" icon={ChevronRight} disabled={offset + 25 >= page.total} onClick={() => setOffset(offset + 25)} aria-label="Next page" />
        </div>
      )}
    </Card>
  )
}

function SettingsCard() {
  const settings = useQuery({ queryKey: ['admin-settings'], queryFn: api.admin.settings })
  if (!settings.data) return <Card className="grid h-40 place-items-center p-5"><Spinner /></Card>
  return <SettingsForm key={JSON.stringify(settings.data)} saved={settings.data} />
}

function SettingsForm({ saved }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(saved)
  const save = useMutation({
    mutationFn: api.admin.saveSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(['admin-settings'], data)
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  })
  const dirty = JSON.stringify(form) !== JSON.stringify(saved)
  const num = (field) => (e) => setForm({ ...form, [field]: Math.max(0, Number(e.target.value || 0)) })
  return (
    <Card className="p-5">
      <h3 className="text-sm font-semibold">Global settings</h3>
      <p className="mt-0.5 text-xs text-muted">Apply to every user on the DocuLens Groq key. Users with their own key are not limited.</p>
      <div className="mt-4 space-y-4">
        <label className="flex items-center justify-between gap-4 text-sm">
          <span>
            <span className="font-medium">AI analysis enabled</span>
            <span className="block text-xs text-muted">When off, analyses use the built-in rules only.</span>
          </span>
          <Switch checked={form.ai_enabled} onCheckedChange={(v) => setForm({ ...form, ai_enabled: v })} />
        </label>
        <label className="flex items-center justify-between gap-4 text-sm">
          <span className="font-medium">Default AI analyses per user per day</span>
          <input type="number" min={0} value={form.default_ai_daily_limit} onChange={num('default_ai_daily_limit')} className="h-9 w-20 rounded-md border border-line bg-surface-2 px-2 text-sm outline-none focus:border-accent" />
        </label>
        <label className="flex items-center justify-between gap-4 text-sm">
          <span className="font-medium">AI chat answers per user per day</span>
          <input type="number" min={0} value={form.chat_daily_limit} onChange={num('chat_daily_limit')} className="h-9 w-20 rounded-md border border-line bg-surface-2 px-2 text-sm outline-none focus:border-accent" />
        </label>
      </div>
      {save.error && <Callout tone="error" className="mt-3">{save.error.message}</Callout>}
      <div className="mt-4 flex justify-end">
        <Button variant="primary" size="sm" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate(form)}>Save settings</Button>
      </div>
    </Card>
  )
}

export default function Admin() {
  const kpis = useQuery({ queryKey: ['admin-kpis'], queryFn: api.admin.kpis, refetchInterval: 60_000 })
  if (kpis.isLoading) return <div className="grid min-h-[60vh] place-items-center"><Spinner className="size-6" /></div>
  if (kpis.isError) return <div className="mx-auto max-w-lg px-5 py-20"><Callout tone="error">{kpis.error.message}</Callout></div>
  const k = kpis.data
  const mode = [
    { name: 'AI (hybrid)', value: k.analyses_ai },
    { name: 'Local rules', value: k.analyses_local },
  ].filter((d) => d.value > 0)
  const daily = k.daily.map((d) => ({ ...d, label: d.day.slice(5) }))

  return (
    <div className="mx-auto max-w-[1300px] space-y-5 px-5 py-8" data-testid="admin-dashboard">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-bold tracking-tight">Admin dashboard</h1>
          <p className="mt-1 text-sm text-muted">Aggregate usage only. Administrators cannot open users' documents or reports.</p>
        </div>
        <span className="text-xs text-muted">Refreshes every minute</span>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Kpi icon={Users} label="Users" value={k.users_total} hint={`${k.users_blocked} blocked`} />
        <Kpi icon={UserPlus} label="New (7 days)" value={k.users_new_7d} hint={`${k.users_new_30d} in 30 days`} tone="text-high" />
        <Kpi icon={Activity} label="Active today" value={k.users_active_today} hint={`${k.users_active_7d} this week`} tone="text-ok" />
        <Kpi icon={FileText} label="Analyses" value={k.analyses_total} hint={`${k.analyses_today} today`} />
        <Kpi icon={Sparkles} label="AI share" value={k.analyses_total ? `${Math.round((100 * k.analyses_ai) / k.analyses_total)}%` : '–'} hint={`${k.users_with_own_key} users with own key`} tone="text-ok" />
        <Kpi icon={AlertTriangle} label="AI fallbacks (30d)" value={k.llm_fallbacks_30d} hint={`${k.analyses_failed} failed analyses`} tone="text-caution" />
        <Kpi icon={Cpu} label="Average score" value={k.average_score ?? '–'} hint={`${k.chats_30d} chats · ${k.pdf_exports_30d} PDFs (30d)`} />
        <Kpi icon={HardDrive} label="Storage" value={bytes(k.storage_bytes)} hint={`${k.documents_total} documents`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <ChartCard title="Last 30 days" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={daily} margin={{ left: -16, right: 8 }}>
              <CartesianGrid vertical={false} stroke={CHART.grid} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: CHART.muted }} interval={4} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: CHART.muted }} />
              <ChartTooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="analyses" name="Analyses" stroke={CHART.ink} fill={CHART.ink} fillOpacity={0.08} strokeWidth={2} />
              <Area type="monotone" dataKey="ai_analyses" name="AI analyses" stroke={CHART.ai} fill={CHART.ai} fillOpacity={0.12} strokeWidth={2} />
              <Area type="monotone" dataKey="signups" name="Sign-ups" stroke={CHART.signups} fill={CHART.signups} fillOpacity={0.1} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="AI vs local analyses">
          {mode.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={mode} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={mode.length > 1 ? 2 : 0} stroke="none">
                  {mode.map((d, i) => <Cell key={d.name} fill={PIE[i]} />)}
                </Pie>
                <ChartTooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="grid h-60 place-items-center text-sm text-muted">No analyses yet</div>
          )}
        </ChartCard>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <ChartCard title="Document types"><Mix data={k.doc_types} empty="No analyses yet" /></ChartCard>
        <ChartCard title="Jurisdictions"><Mix data={k.jurisdictions} empty="No analyses yet" /></ChartCard>
        <ChartCard title="Grades"><Mix data={k.grades} empty="No analyses yet" /></ChartCard>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <UsersTable />
        <SettingsCard />
      </div>
    </div>
  )
}
