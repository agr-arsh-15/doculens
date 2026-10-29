import { useQuery } from '@tanstack/react-query'
import { ArrowLeftRight, GitCompareArrows } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button, Callout, Card, Chip, cx, EmptyState, GradeSeal, Meter, Select, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { SEVERITY, scoreTone } from '../lib/format'

const VERDICT = {
  a_better: { label: 'A is safer', cls: 'bg-ok-soft text-ok' },
  b_better: { label: 'B is safer', cls: 'bg-ok-soft text-ok' },
  same: { label: 'Similar', cls: 'bg-sunken text-ink-2' },
  only_a: { label: 'Only in A', cls: 'bg-accent-soft text-accent' },
  only_b: { label: 'Only in B', cls: 'bg-accent-soft text-accent' },
}

function Cell({ cell, side, verdict }) {
  if (!cell) return <div className="text-sm italic text-faint">Not present</div>
  const better = (side === 'a' && verdict === 'a_better') || (side === 'b' && verdict === 'b_better')
  return (
    <div className={cx('rounded-lg p-3', better ? 'bg-ok-soft/50' : 'bg-surface-2')}>
      {cell.missing && !cell.clause_ids.length ? (
        <div className="text-sm font-medium text-caution">Missing from this document</div>
      ) : (
        cell.heading && <div className="text-xs font-medium text-muted">{cell.heading}</div>
      )}
      {cell.findings.length > 0 ? (
        <ul className="mt-1.5 space-y-1">
          {cell.findings.slice(0, 4).map((t) => (
            <li key={t} className="flex items-start gap-2 text-[13px] leading-snug">
              <span className={cx('mt-1.5 size-1.5 shrink-0 rounded-full', SEVERITY[cell.worst]?.bg || 'bg-info')} />
              {t}
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-1 text-[13px] text-ok">No issues found</div>
      )}
      {cell.excerpt && <p className="mt-2 line-clamp-2 font-serif text-[13px] italic text-muted">{cell.excerpt}</p>}
    </div>
  )
}

function Side({ side, label }) {
  return (
    <Card className="flex items-center gap-4 p-5">
      <GradeSeal grade={side.grade} score={side.overall} size="sm" />
      <div className="min-w-0">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Document {label}</div>
        <Link to={`/report/${side.analysis_id}`} className="block truncate font-semibold hover:underline">{side.filename}</Link>
        <div className="mt-0.5 text-xs text-muted">
          {side.doc_type_label} · {side.jurisdiction_label} · as {side.perspective_label} · <span className="font-mono">{side.overall}/100</span>
        </div>
      </div>
    </Card>
  )
}

export default function Compare() {
  const [params, setParams] = useSearchParams()
  const a = params.get('a') || ''
  const b = params.get('b') || ''
  const history = useQuery({ queryKey: ['analyses', ''], queryFn: () => api.analyses('') })
  const result = useQuery({ queryKey: ['compare', a, b], queryFn: () => api.compare(a, b), enabled: !!a && !!b && a !== b })

  const options = [{ value: '', label: 'Choose an analysis...' }].concat(
    (history.data || [])
      .filter((h) => h.status === 'completed')
      .map((h) => ({ value: h.id, label: `${h.filename} · ${h.doc_type_label} · ${h.grade} (${h.overall})` })),
  )
  const set = (key, value) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const r = result.data
  return (
    <div className="mx-auto max-w-[1300px] px-5 py-8">
      <h1 className="font-serif text-3xl font-bold tracking-tight">Compare documents</h1>
      <p className="mt-1 text-ink-2">Line up two analyses clause by clause, for example two offer letters or two vendors' contracts.</p>

      <Card className="mt-6 grid items-end gap-4 p-5 md:grid-cols-[1fr_auto_1fr]">
        <label className="block">
          <span className="mb-1.5 block text-[13px] font-semibold uppercase tracking-wide text-muted">Document A</span>
          <Select value={a} onChange={(v) => set('a', v)} options={options} className="w-full" />
        </label>
        <button
          className="mb-1 grid size-9 cursor-pointer place-items-center rounded-lg text-muted hover:bg-sunken hover:text-ink"
          onClick={() => setParams({ ...(b && { a: b }), ...(a && { b: a }) }, { replace: true })}
          aria-label="Swap"
        >
          <ArrowLeftRight className="size-4" />
        </button>
        <label className="block">
          <span className="mb-1.5 block text-[13px] font-semibold uppercase tracking-wide text-muted">Document B</span>
          <Select value={b} onChange={(v) => set('b', v)} options={options} className="w-full" />
        </label>
      </Card>

      {history.data && options.length < 3 && (
        <Callout tone="info" className="mt-4" action={<Button as={Link} to="/" size="sm">Analyze a document</Button>}>
          You need at least two completed analyses to compare.
        </Callout>
      )}

      {!a || !b ? (
        <EmptyState icon={GitCompareArrows} title="Pick two analyses">Choose document A and document B above.</EmptyState>
      ) : a === b ? (
        <Callout tone="warning" className="mt-6">Choose two different analyses.</Callout>
      ) : result.isLoading ? (
        <div className="grid h-64 place-items-center"><Spinner className="size-6" /></div>
      ) : result.isError ? (
        <Callout tone="error" className="mt-6">{result.error.message}</Callout>
      ) : r ? (
        <div className="mt-6 space-y-6" data-testid="compare-result">
          <div className="grid gap-4 md:grid-cols-2">
            <Side side={r.a} label="A" />
            <Side side={r.b} label="B" />
          </div>
          <Card className="p-5">
            <p className="font-serif text-lg">{r.headline}</p>
            {r.warnings.map((w) => <Callout key={w} tone="warning" className="mt-3">{w}</Callout>)}
            <div className="mt-5 grid gap-x-8 gap-y-3 md:grid-cols-2">
              {r.a.categories.map((c, i) => {
                const other = r.b.categories[i]
                return (
                  <div key={c.id} className="text-sm">
                    <div className="mb-1 flex justify-between"><span className="text-ink-2">{c.label}</span><span className="font-mono text-xs">A {c.score} · B {other?.score}</span></div>
                    <div className="space-y-1">
                      <Meter value={c.score} tone={scoreTone(c.score)} />
                      <Meter value={other?.score ?? 0} tone={scoreTone(other?.score ?? 0)} />
                    </div>
                  </div>
                )
              })}
            </div>
          </Card>

          <Card className="overflow-hidden">
            <div className="grid grid-cols-[180px_1fr_110px_1fr] gap-4 border-b border-line bg-surface-2 px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-muted max-md:hidden">
              <span>Clause area</span><span>Document A</span><span className="text-center">Verdict</span><span>Document B</span>
            </div>
            {r.rows.map((row) => (
              <div key={row.key} className="grid gap-3 border-b border-line px-5 py-4 last:border-0 md:grid-cols-[180px_1fr_110px_1fr] md:gap-4">
                <div className="font-semibold">{row.label}{row.similarity != null && <div className="text-[11px] font-normal text-muted">aligned by similarity {row.similarity}</div>}</div>
                <Cell cell={row.a} side="a" verdict={row.verdict} />
                <div className="flex items-start justify-center"><span className={cx('rounded-full px-2.5 py-1 text-[11px] font-semibold', VERDICT[row.verdict].cls)}>{VERDICT[row.verdict].label}</span></div>
                <Cell cell={row.b} side="b" verdict={row.verdict} />
              </div>
            ))}
          </Card>

          {r.benchmarks.length > 0 && (
            <Card className="p-5">
              <h3 className="mb-3 font-semibold">Market terms side by side</h3>
              <table className="w-full text-sm">
                <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
                  <tr><th className="py-2">Term</th><th>A</th><th>B</th><th>Better</th></tr>
                </thead>
                <tbody>
                  {r.benchmarks.map((m) => (
                    <tr key={m.metric_id} className="border-t border-line">
                      <td className="py-2">{m.label}</td>
                      <td className={cx(m.a_assessment === 'unfavorable' && 'text-high')}>{m.a_display || '—'}</td>
                      <td className={cx(m.b_assessment === 'unfavorable' && 'text-high')}>{m.b_display || '—'}</td>
                      <td>{m.better ? <Chip>{m.better === 'same' ? 'Same' : m.better.toUpperCase()}</Chip> : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      ) : null}
    </div>
  )
}
