import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, GitCompareArrows, History as HistoryIcon, Search, Trash2 } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Callout, Card, Chip, cx, EmptyState, GradeSeal, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { relativeTime, SEVERITY } from '../lib/format'

export default function History() {
  const [q, setQ] = useState('')
  const query = useDeferredValue(q)
  const [picked, setPicked] = useState([])
  const navigate = useNavigate()
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['analyses', query], queryFn: () => api.analyses(query), refetchInterval: (s) => (s.state.data?.some((x) => x.status === 'running' || x.status === 'queued') ? 3000 : false) })
  const remove = useMutation({ mutationFn: api.deleteAnalysis, onSuccess: () => qc.invalidateQueries({ queryKey: ['analyses'] }) })

  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p.slice(-1), id]))

  return (
    <div className="mx-auto max-w-[1100px] px-5 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl font-bold tracking-tight">History</h1>
          <p className="mt-1 text-ink-2">Every analysis is saved on your DocuLens server. Select two to compare.</p>
        </div>
        <Button variant="primary" icon={GitCompareArrows} disabled={picked.length !== 2} onClick={() => navigate(`/compare?a=${picked[0]}&b=${picked[1]}`)}>
          Compare selected ({picked.length}/2)
        </Button>
      </div>

      <div className="relative mt-6">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by file name, document type or jurisdiction..."
          className="h-11 w-full rounded-xl border border-line bg-surface pl-10 pr-4 text-sm outline-none focus:border-accent"
        />
      </div>

      <div className="mt-4 space-y-2.5">
        {list.isLoading && <div className="grid h-40 place-items-center"><Spinner /></div>}
        {list.isError && <Callout tone="error">{list.error.message}</Callout>}
        {list.data?.length === 0 && (
          <EmptyState icon={HistoryIcon} title={query ? 'No matches' : 'No analyses yet'} action={!query && <Button as={Link} to="/" variant="primary">Analyze a document</Button>}>
            {query ? 'Try a different search.' : 'Upload or paste a document to get started.'}
          </EmptyState>
        )}
        {list.data?.map((h) => {
          const counts = h.finding_counts || {}
          const done = h.status === 'completed'
          return (
            <Card key={h.id} className={cx('flex items-center gap-4 p-4 transition-colors', picked.includes(h.id) && 'border-ink ring-1 ring-ink')}>
              <input
                type="checkbox"
                disabled={!done}
                checked={picked.includes(h.id)}
                onChange={() => toggle(h.id)}
                className="size-4 cursor-pointer accent-[var(--ink)]"
                aria-label={`Select ${h.filename}`}
              />
              {done ? <GradeSeal grade={h.grade} score={h.overall} size="sm" /> : (
                <div className="grid size-14 place-items-center rounded-full bg-sunken"><FileText className="size-5 text-muted" /></div>
              )}
              <Link to={done ? `/report/${h.id}` : `/analyze/${h.document_id}`} className="min-w-0 flex-1">
                <div className="truncate font-semibold hover:underline">{h.filename}</div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
                  <span>{h.doc_type_label}</span>·<span>{h.jurisdiction}</span>·<span>as {h.perspective}</span>·<span>{relativeTime(h.created_at)}</span>
                  {h.engine_mode && <><span>·</span><span>{h.engine_mode === 'hybrid' ? 'Hybrid AI' : 'Local'}</span></>}
                </div>
              </Link>
              <div className="hidden flex-wrap justify-end gap-1.5 md:flex">
                {done ? (
                  ['critical', 'high', 'medium'].map((s) =>
                    counts[s] ? (
                      <span key={s} className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', SEVERITY[s].soft, SEVERITY[s].text)}>
                        {counts[s]} {SEVERITY[s].label.toLowerCase()}
                      </span>
                    ) : null,
                  )
                ) : (
                  <Chip tone={h.status === 'failed' ? 'critical' : undefined}>{h.status}</Chip>
                )}
                {counts.hidden ? <Chip>{counts.hidden} hidden</Chip> : null}
              </div>
              <button
                onClick={() => remove.mutate(h.id)}
                className="grid size-8 cursor-pointer place-items-center rounded-lg text-faint hover:bg-critical-soft hover:text-critical"
                aria-label={`Delete ${h.filename}`}
              >
                <Trash2 className="size-4" />
              </button>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
