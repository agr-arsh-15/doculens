import { Cpu, Globe2, Handshake, Sparkles, User } from 'lucide-react'
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from 'recharts'
import { RISK_LEVEL, SEVERITY, TONE, scoreTone } from '../../lib/format'
import { Card, Chip, cx, GradeSeal, Tooltip } from '../ui'

function Counts({ findings }) {
  const risky = findings.filter((f) => !f.favorable)
  const items = [
    ['critical', risky.filter((f) => f.severity === 'critical').length],
    ['high', risky.filter((f) => f.severity === 'high').length],
    ['medium', risky.filter((f) => f.severity === 'medium' || f.severity === 'low').length],
  ]
  const hidden = risky.filter((f) => f.kind === 'hidden').length
  const missing = risky.filter((f) => f.kind === 'missing').length
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
      {items.map(([sev, n]) => (
        <div key={sev} className="flex items-center gap-2">
          <span className={cx('size-2.5 rounded-full', SEVERITY[sev].bg)} />
          <span className="font-semibold tabular-nums">{n}</span>
          <span className="text-muted">{SEVERITY[sev].label.toLowerCase()}</span>
        </div>
      ))}
      <div className="flex items-center gap-2"><span className="font-semibold tabular-nums">{hidden}</span><span className="text-muted">hidden</span></div>
      <div className="flex items-center gap-2"><span className="font-semibold tabular-nums">{missing}</span><span className="text-muted">missing</span></div>
    </div>
  )
}

function RadarTick({ x, y, textAnchor, payload }) {
  const label = payload.value
  const lines = label.includes(' & ') ? [label.split(' & ')[0] + ' &', label.split(' & ')[1]] : [label]
  return (
    <text x={x} y={y - (lines.length - 1) * 6} textAnchor={textAnchor} fill="var(--muted)" fontSize={10.5}>
      {lines.map((line, i) => <tspan key={line} x={x} dy={i ? 12 : 0}>{line}</tspan>)}
    </text>
  )
}

export default function Scorecard({ result, onSelectFinding }) {
  const card = result.scorecard
  const level = RISK_LEVEL[card.risk_level]
  const radarData = card.categories.map((c) => ({ label: c.label, score: c.score, full: 100 }))
  const byId = Object.fromEntries(result.findings.map((f) => [f.id, f]))
  const top = card.top_negotiation.map((id) => byId[id]).filter(Boolean)
  const engine = result.engine
  const hybrid = engine.mode === 'hybrid'

  return (
    <Card className="overflow-hidden" data-testid="scorecard">
      <div className="grid gap-6 p-6 lg:grid-cols-[auto_1fr_300px]">
        <div className="flex flex-col items-center gap-3 lg:pr-2">
          <GradeSeal grade={card.grade} score={card.overall} />
          <span className={cx('rounded-full px-3 py-1 text-xs font-semibold', TONE[level.tone].soft, TONE[level.tone].text)}>{level.label}</span>
        </div>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip>{result.doc_type_label}</Chip>
            <Chip icon={Globe2}>{result.jurisdiction_label}</Chip>
            <Chip icon={User}>Read as {result.perspective_label}</Chip>
            <Tooltip
              content={
                hybrid
                  ? `Rules + ${engine.embedding_backend} embeddings + ${engine.llm_provider} (${engine.llm_model}). ${engine.llm_findings_rejected_unverified} AI finding(s) rejected because their quotes could not be verified.`
                  : `Rules + ${engine.embedding_backend} embeddings. Add an LLM key for deeper AI reasoning.`
              }
            >
              <span>
                <Chip icon={hybrid ? Sparkles : Cpu} tone={hybrid ? 'ok' : undefined} className="cursor-help">
                  {hybrid ? 'Hybrid AI' : 'Local mode'}
                </Chip>
              </span>
            </Tooltip>
          </div>
          <h1 className="mt-3 truncate font-serif text-2xl font-bold tracking-tight" data-testid="report-title">{result.filename}</h1>
          <p className="mt-2 max-w-3xl text-[15px] leading-relaxed text-ink-2" data-testid="report-summary">{result.summary}</p>
          <div className="mt-4">
            <Counts findings={result.findings} />
          </div>
        </div>

        <div className="h-[230px] min-w-0">
          <div className="text-center text-[11px] font-semibold uppercase tracking-wide text-muted">Safety by category</div>
          <ResponsiveContainer width="100%" height="94%">
            <RadarChart data={radarData} outerRadius="66%">
              <PolarGrid stroke="var(--line-strong)" />
              <PolarAngleAxis dataKey="label" tick={<RadarTick />} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Radar dataKey="full" stroke="none" fill="var(--line)" fillOpacity={0.25} isAnimationActive={false} />
              <Radar dataKey="score" stroke={TONE[scoreTone(card.overall)].color} fill={TONE[scoreTone(card.overall)].color} fillOpacity={0.28} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {top.length > 0 && (
        <div className="border-t border-line bg-surface-2 px-6 py-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Handshake className="size-4" /> Top {top.length} things to negotiate
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {top.map((f, i) => (
              <button
                key={f.id}
                onClick={() => onSelectFinding(f.id)}
                className="group cursor-pointer rounded-xl border border-line bg-surface p-3.5 text-left transition-colors hover:border-ink"
              >
                <div className="flex items-start gap-3">
                  <span className="font-serif text-2xl font-bold leading-none text-faint group-hover:text-ink">{i + 1}</span>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold leading-snug">{f.title}</div>
                    <div className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{f.recommendation}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}
