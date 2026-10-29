import * as Popover from '@radix-ui/react-popover'
import { useQuery } from '@tanstack/react-query'
import {
  Cpu, GitCompareArrows, History, LayoutDashboard, LogIn, LogOut, Moon, ScanSearch, Settings, Sparkles, Sun, WifiOff,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { api, onSlowRequests } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useTheme } from '../lib/theme'
import { Button, cx, Spinner, Tooltip } from './ui'

function Logo() {
  return (
    <Link to="/" className="group flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8">
        <rect width="32" height="32" rx="8" fill="var(--ink)" />
        <path d="M9 7h9l5 5v13H9z" fill="var(--paper)" />
        <path d="M18 7v5h5" fill="var(--line-strong)" />
        <rect x="11.5" y="15" width="9" height="2.4" rx="1" fill="var(--high)" />
        <rect x="11.5" y="19.5" width="6" height="1.6" rx=".8" fill="var(--faint)" />
      </svg>
      <div className="leading-none">
        <div className="font-serif text-[19px] font-bold tracking-tight">DocuLens</div>
        <div className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-muted">Document X-Ray</div>
      </div>
    </Link>
  )
}

function EngineStatus() {
  const { data, isError } = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 30000, retry: 1 })
  if (isError) {
    return (
      <Tooltip content="The DocuLens server is not reachable right now. If it was idle it may be starting up; try again in a minute.">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-critical-soft px-2.5 py-1 text-xs font-medium text-critical">
          <WifiOff className="size-3.5" /> API offline
        </span>
      </Tooltip>
    )
  }
  if (!data) return null
  const hybrid = data.llm?.enabled
  const tip = hybrid
    ? `Hybrid mode: playbook rules + ${data.embeddings?.backend} embeddings + ${data.llm.provider} (${data.llm.model}).`
    : `Local mode: playbook rules + ${data.embeddings?.backend} embeddings. ${data.llm?.hint || ''}`
  return (
    <Tooltip content={tip}>
      <span
        className={cx(
          'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
          hybrid ? 'bg-ok-soft text-ok' : 'bg-sunken text-ink-2',
        )}
      >
        {hybrid ? <Sparkles className="size-3.5" /> : <Cpu className="size-3.5" />}
        {hybrid ? 'Hybrid AI' : 'Local mode'}
      </span>
    </Tooltip>
  )
}

const NAV = [
  { to: '/', label: 'Analyze', icon: ScanSearch, end: true },
  { to: '/compare', label: 'Compare', icon: GitCompareArrows, private: true },
  { to: '/history', label: 'History', icon: History, private: true },
]

function initials(user) {
  const source = user?.name || user?.email || '?'
  return source.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('')
}

function AccountMenu() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  if (!auth.signedIn) {
    if (location.pathname === '/login') return null
    return (
      <Button size="sm" variant="primary" icon={LogIn} onClick={() => navigate(`/login?next=${encodeURIComponent(location.pathname)}`)} data-testid="header-sign-in">
        Sign in
      </Button>
    )
  }
  const user = auth.user
  const item = 'flex w-full cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-ink-2 hover:bg-sunken hover:text-ink'
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button className="grid size-9 cursor-pointer place-items-center overflow-hidden rounded-full border border-line bg-surface text-xs font-semibold text-ink-2 hover:border-line-strong" aria-label="Account menu" data-testid="account-menu">
          {user?.avatar_url ? <img src={user.avatar_url} alt="" referrerPolicy="no-referrer" className="size-full object-cover" /> : initials(user)}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} className="z-50 w-64 rounded-xl border border-line bg-surface p-1.5 shadow-xl">
          <div className="border-b border-line px-2.5 pb-2.5 pt-1.5">
            <div className="truncate text-sm font-semibold">{user?.name || 'Signed in'}</div>
            <div className="truncate text-xs text-muted">{user?.email}</div>
          </div>
          <div className="pt-1.5" onClick={() => setOpen(false)}>
            <Link to="/settings" className={item}><Settings className="size-4" /> Settings</Link>
            {auth.isAdmin && <Link to="/admin" className={item} data-testid="admin-link"><LayoutDashboard className="size-4" /> Admin dashboard</Link>}
            {auth.mode !== 'local' && (
              <button className={item} onClick={async () => { await auth.signOut(); navigate('/') }} data-testid="sign-out">
                <LogOut className="size-4" /> Sign out
              </button>
            )}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}

function WakingBanner() {
  const [slow, setSlow] = useState(false)
  useEffect(() => onSlowRequests(setSlow), [])
  if (!slow) return null
  return (
    <div className="no-print border-b border-line bg-caution-soft/70 px-5 py-2 text-center text-xs text-ink-2" role="status">
      <Spinner className="mr-2 inline size-3.5 align-[-2px]" />
      Waking up the server. The free hosting tier sleeps when idle, so the first request can take up to a minute.
    </div>
  )
}

export default function AppShell() {
  const { dark, toggle } = useTheme()
  const auth = useAuth()
  const nav = NAV.filter((n) => !n.private || auth.signedIn)
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1500px] items-center gap-6 px-5">
          <Logo />
          <nav className="ml-4 hidden items-center gap-1 sm:flex">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cx(
                    'inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                    isActive ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink',
                  )
                }
              >
                <Icon className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <EngineStatus />
            <button
              onClick={toggle}
              className="grid size-9 cursor-pointer place-items-center rounded-lg text-muted hover:bg-sunken hover:text-ink"
              aria-label="Toggle dark mode"
            >
              {dark ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
            </button>
            <AccountMenu />
          </div>
        </div>
        <nav className="flex items-center gap-1 border-t border-line px-3 py-1.5 sm:hidden">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cx('inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium', isActive ? 'bg-surface text-ink' : 'text-muted')
              }
            >
              <Icon className="size-3.5" />
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <WakingBanner />
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="no-print border-t border-line">
        <div className="mx-auto max-w-[1500px] px-5 py-5 text-center text-xs text-muted">
          DocuLens · Document X-Ray. Automated risk analysis for information only; it is not legal advice.
          <span className="mx-2 text-faint">·</span>
          <Link to="/privacy" className="hover:text-ink hover:underline">Privacy</Link>
          <span className="mx-2 text-faint">·</span>
          <Link to="/terms" className="hover:text-ink hover:underline">Terms</Link>
        </div>
      </footer>
    </div>
  )
}
