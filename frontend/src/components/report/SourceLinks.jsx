import { ExternalLink } from 'lucide-react'
import { cx } from '../ui'

const TIER_LABEL = {
  official: 'Official',
  professional: 'Professional body',
  law_firm: 'Law firm',
  news: 'News',
}

export default function SourceLinks({ sources, className, compact = false }) {
  const linked = (sources || []).filter((s) => s.url)
  if (!linked.length) return null
  return (
    <ul className={cx('space-y-1.5', className)} data-testid="source-links">
      {linked.map((s) => (
        <li key={s.id || s.url} className="flex items-start gap-2 text-xs leading-snug">
          {s.tier && (
            <span className="mt-px shrink-0 rounded bg-sunken px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide text-muted">
              {TIER_LABEL[s.tier] || s.tier}
            </span>
          )}
          <a
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="group inline-flex min-w-0 items-start gap-1 text-ink-2 hover:text-ink"
          >
            <span className="underline decoration-line-strong underline-offset-2 group-hover:decoration-ink">
              {s.title}
              {!compact && s.publisher && <span className="text-muted"> · {s.publisher}</span>}
            </span>
            <ExternalLink className="mt-0.5 size-3 shrink-0 text-faint" />
          </a>
        </li>
      ))}
    </ul>
  )
}
