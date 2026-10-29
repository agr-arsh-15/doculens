import { useQuery } from '@tanstack/react-query'
import { Cpu, GitCompareArrows, History, Moon, ScanSearch, Sparkles, Sun, WifiOff } from 'lucide-react'
import { NavLink, Outlet, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useTheme } from '../lib/theme'
import { cx, Tooltip } from './ui'

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
      <Tooltip content="The DocuLens API is not reachable. Start it with ./start.sh (or python backend/run.py).">
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
  { to: '/compare', label: 'Compare', icon: GitCompareArrows },
  { to: '/history', label: 'History', icon: History },
]

export default function AppShell() {
  const { dark, toggle } = useTheme()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1500px] items-center gap-6 px-5">
          <Logo />
          <nav className="ml-4 hidden items-center gap-1 sm:flex">
            {NAV.map(({ to, label, icon: Icon, end }) => (
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
          </div>
        </div>
        <nav className="flex items-center gap-1 border-t border-line px-3 py-1.5 sm:hidden">
          {NAV.map(({ to, label, icon: Icon, end }) => (
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
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="no-print border-t border-line">
        <div className="mx-auto max-w-[1500px] px-5 py-5 text-center text-xs text-muted">
          DocuLens · Document X-Ray. Automated risk analysis for information only; it is not legal advice.
        </div>
      </footer>
    </div>
  )
}
