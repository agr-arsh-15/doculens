import { CheckCircle2, EyeOff, FileWarning, Scale, ShieldAlert } from 'lucide-react'
import { useEffect, useMemo, useRef } from 'react'
import { EmptyState, Tabs } from '../ui'
import FindingCard from './FindingCard'
import MarketItem from './MarketItem'

function groupFindings(findings) {
  const risks = findings.filter((f) => !f.favorable && f.kind !== 'missing').sort((a, b) => b.score_impact - a.score_impact)
  return {
    risks,
    hidden: risks.filter((f) => f.kind === 'hidden'),
    missing: findings.filter((f) => f.kind === 'missing' && !f.favorable),
    favorable: findings.filter((f) => f.favorable),
  }
}

const EMPTY_COPY = {
  risks: [ShieldAlert, 'No risky clauses found', 'Nothing in this document triggered a risk for your side.'],
  hidden: [EyeOff, 'Nothing hidden', 'No buried clauses, vague discretion or external terms were detected.'],
  missing: [FileWarning, 'Nothing missing', 'All the clauses we expect for this document type are present.'],
  market: [Scale, 'No measurable terms', 'We did not find durations or amounts we can compare with market ranges.'],
  favorable: [CheckCircle2, 'No favorable terms flagged', 'Terms that work in your favor will show up here.'],
}

export default function FindingsRail({ findings, benchmarks, tab, onTab, activeId, onSelect, onJumpClause, onJumpBenchmark }) {
  const groups = useMemo(() => groupFindings(findings), [findings])
  const refs = useRef({})
  const scroller = useRef(null)

  useEffect(() => {
    const el = activeId && refs.current[activeId]
    if (el && scroller.current) {
      const top = el.offsetTop - 12
      scroller.current.scrollTo({ top, behavior: 'smooth' })
    }
  }, [activeId, tab])

  const tabs = [
    { value: 'risks', label: 'Risks', count: groups.risks.length, countClass: groups.risks.length ? 'bg-high-soft text-high' : undefined },
    { value: 'hidden', label: 'Hidden', count: groups.hidden.length },
    { value: 'missing', label: 'Missing', count: groups.missing.length },
    { value: 'market', label: 'Market', count: benchmarks.length },
    { value: 'favorable', label: 'In favor', count: groups.favorable.length },
  ]
  const list = tab === 'market' ? benchmarks : groups[tab] || []
  const [Icon, title, body] = EMPTY_COPY[tab]

  return (
    <div className="flex h-full flex-col">
      <Tabs value={tab} onValueChange={onTab} tabs={tabs} listClassName="text-xs" />
      <div ref={scroller} className="scrollbar-thin relative mt-3 flex-1 space-y-2.5 overflow-y-auto pb-6 pr-1" data-testid="findings-rail">
        {list.length === 0 && <EmptyState icon={Icon} title={title}>{body}</EmptyState>}
        {tab === 'market'
          ? list.map((b) => <MarketItem key={b.metric_id} item={b} onJump={onJumpBenchmark} />)
          : list.map((f) => (
              <FindingCard
                key={f.id}
                ref={(el) => (refs.current[f.id] = el)}
                finding={f}
                active={f.id === activeId}
                onSelect={(id) => onSelect(id, 'rail')}
                onJumpClause={onJumpClause}
              />
            ))}
      </div>
    </div>
  )
}
