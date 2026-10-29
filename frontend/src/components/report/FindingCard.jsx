import { BadgeCheck, BookOpen, ChevronDown, EyeOff, FileWarning, PenLine, Scale, Sparkles } from 'lucide-react'
import { forwardRef } from 'react'
import { SOURCE_LABEL, severityMeta } from '../../lib/format'
import { Chip, cx, SeverityBadge, Tooltip } from '../ui'
import SourceLinks from './SourceLinks'

function Section({ label, icon: Icon, children, className }) {
  return (
    <div className={className}>
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {Icon && <Icon className="size-3.5" />}
        {label}
      </div>
      <div className="text-[13.5px] leading-relaxed text-ink-2">{children}</div>
    </div>
  )
}

const FindingCard = forwardRef(function FindingCard({ finding: f, active, onSelect, onJumpClause }, ref) {
  const meta = severityMeta(f)
  const aiOnly = f.sources?.includes('llm') && !f.sources?.includes('rule')
  const refs = (f.references || []).map((r) => (typeof r === 'string' ? { title: r } : r))
  const linked = refs.filter((r) => r.url)
  const unlinked = refs.filter((r) => !r.url)
  return (
    <article
      ref={ref}
      id={`finding-${f.id}`}
      data-testid="finding-card"
      onClick={() => onSelect(f.id)}
      className={cx(
        'group relative cursor-pointer rounded-xl border bg-surface p-4 transition-all',
        active ? 'border-ink shadow-card ring-1 ring-ink' : 'border-line hover:border-line-strong',
      )}
    >
      <span className="absolute left-0 top-4 h-6 w-[3px] rounded-r-full" style={{ background: meta.color }} />
      <div className="flex flex-wrap items-center gap-1.5">
        <SeverityBadge finding={f} />
        {f.kind === 'hidden' && (
          <Chip className="py-0 text-[11px]" icon={EyeOff}>{f.buried ? 'Buried' : 'Hidden'}</Chip>
        )}
        {f.kind === 'missing' && <Chip className="py-0 text-[11px]" icon={FileWarning}>Missing</Chip>}
        {f.kind === 'benchmark' && <Chip className="py-0 text-[11px]" icon={Scale}>Off-market</Chip>}
        <span className="ml-auto font-mono text-[11px] text-faint">{f.id}</span>
      </div>

      <h3 className="mt-2 font-semibold leading-snug text-ink">{f.title}</h3>
      {f.clause_label && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onJumpClause(f)
          }}
          className="mt-0.5 cursor-pointer text-xs text-muted hover:text-ink hover:underline"
          disabled={f.kind === 'missing'}
        >
          {f.kind === 'missing' ? `Expected: ${f.clause_label}` : `${f.clause_label}${f.clause_ids?.[0] ? ` · ${f.clause_ids[0]}` : ''}`}
        </button>
      )}

      {f.quote && f.kind !== 'missing' && (
        <blockquote className={cx('mt-3 border-l-2 pl-3 font-serif text-[14.5px] italic leading-relaxed text-ink-2', !active && 'line-clamp-3')} style={{ borderColor: meta.color }}>
          "{f.quote}"
        </blockquote>
      )}

      <p className={cx('mt-3 text-[13.5px] leading-relaxed text-ink-2', !active && 'line-clamp-2')}>
        {aiOnly && (
          <Tooltip content="Written by the AI model. The quote is verified against your document; the wording of this explanation is not taken from a source.">
            <span className="mr-1.5 inline-flex cursor-help items-center gap-1 rounded bg-sunken px-1.5 py-px align-[1px] text-[10px] font-semibold uppercase tracking-wide text-muted">
              <Sparkles className="size-3" /> AI explanation
            </span>
          </Tooltip>
        )}
        {f.explanation}
      </p>

      {active ? (
        <div className="mt-4 space-y-3 border-t border-line pt-3" onClick={(e) => e.stopPropagation()}>
          {f.hidden_reason && <Section label="Why it is easy to miss" icon={EyeOff}>{f.hidden_reason}</Section>}
          {f.market_comparison && (
            <Section label="Market standard" icon={Scale}>
              <p>{f.market_comparison}</p>
              <SourceLinks sources={linked} className="mt-2" />
            </Section>
          )}
          {!f.market_comparison && linked.length > 0 && (
            <Section label="Sources" icon={BookOpen}>
              <SourceLinks sources={linked} />
            </Section>
          )}
          {f.ai_comparison && (
            <Section label="AI comparison (not from a source)" icon={Sparkles}>{f.ai_comparison}</Section>
          )}
          {f.recommendation && <Section label="What to ask for" icon={PenLine}>{f.recommendation}</Section>}
          {unlinked.length > 0 && (
            <Section label="References" icon={BookOpen}>
              <ul className="list-inside list-disc text-xs text-muted">
                {unlinked.map((r) => <li key={r.title}>{r.title}</li>)}
              </ul>
            </Section>
          )}
          <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-muted">
            <span>Found by {f.sources.map((s) => SOURCE_LABEL[s] || s).join(' + ')}</span>
            <span>·</span>
            <Tooltip content="How sure the engine is that this is a real issue in this document.">
              <span className="cursor-help">{Math.round(f.confidence * 100)}% confidence</span>
            </Tooltip>
            {f.verified && (
              <Tooltip content="The quoted text was matched against the source document.">
                <span className="inline-flex cursor-help items-center gap-1 text-ok">
                  <BadgeCheck className="size-3.5" /> Quote verified
                </span>
              </Tooltip>
            )}
            {f.score_impact > 0 && <span className="ml-auto font-mono">-{f.score_impact.toFixed(1)} pts</span>}
          </div>
        </div>
      ) : (
        <div className="mt-2 flex items-center gap-1 text-xs text-faint group-hover:text-muted">
          <ChevronDown className="size-3.5" /> Details
        </div>
      )}
    </article>
  )
})

export default FindingCard
