import { cx } from '../ui'
import SourceLinks from './SourceLinks'

const ASSESS = {
  favorable: { label: 'In your favor', cls: 'bg-ok-soft text-ok', color: 'var(--ok)' },
  neutral: { label: 'Market standard', cls: 'bg-sunken text-ink-2', color: 'var(--ink-2)' },
  unfavorable: { label: 'Against you', cls: 'bg-high-soft text-high', color: 'var(--high)' },
}

const fmt = (v, unit) => (unit === 'percent' ? `${v}%` : `${Math.round(v * 10) / 10} ${v === 1 ? unit.replace(/s$/, '') : unit}`)

export default function MarketItem({ item, onJump }) {
  const max = Math.max(item.scale_max, item.value, item.market_max ?? 0) || 1
  const pct = (v) => `${Math.min(100, Math.max(0, (v / max) * 100))}%`
  const a = ASSESS[item.assessment]
  const hasRange = item.market_min != null || item.market_max != null
  const lo = item.market_min ?? 0
  const hi = item.market_max ?? max
  return (
    <div
      className="cursor-pointer rounded-xl border border-line bg-surface p-4 transition-colors hover:border-line-strong"
      onClick={() => onJump(item)}
      data-testid="market-item"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold">{item.label}</div>
          <div className="mt-0.5 font-serif text-sm italic text-muted">"{item.display_value}"</div>
        </div>
        <span className={cx('shrink-0 rounded-md px-2 py-0.5 text-[11px] font-semibold', a.cls)}>{a.label}</span>
      </div>

      <div className="relative mb-6 mt-7 h-2 rounded-full bg-line">
        {hasRange && (
          <div
            className="absolute inset-y-0 rounded-full bg-ok/35"
            style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})`, minWidth: 4 }}
          />
        )}
        {item.typical != null && <div className="absolute -top-1 h-4 w-px bg-ok" style={{ left: pct(item.typical) }} />}
        <div className="absolute -top-[22px] -translate-x-1/2 whitespace-nowrap font-mono text-[11px] font-semibold" style={{ left: pct(item.value), color: a.color }}>
          {fmt(item.value, item.unit)}
        </div>
        <div className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface shadow" style={{ left: pct(item.value), background: a.color }} />
        <div className="absolute -bottom-5 left-0 font-mono text-[10px] text-faint">0</div>
        <div className="absolute -bottom-5 right-0 font-mono text-[10px] text-faint">{fmt(Math.round(max), item.unit)}</div>
        {hasRange && (
          <div className="absolute -bottom-5 -translate-x-1/2 whitespace-nowrap text-[10px] font-medium text-ok" style={{ left: `calc((${pct(lo)} + ${pct(hi)}) / 2)` }}>
            market
          </div>
        )}
      </div>
      <p className="text-[13px] leading-relaxed text-ink-2">{item.note}</p>
      {item.sources?.length > 0 && (
        <div className="mt-2.5 border-t border-line pt-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-faint">Market range source</div>
          <SourceLinks sources={item.sources} compact />
        </div>
      )}
    </div>
  )
}
