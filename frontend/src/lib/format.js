export const SEVERITY = {
  critical: { label: 'Critical', rank: 4, text: 'text-critical', bg: 'bg-critical', soft: 'bg-critical-soft', hl: 'hl-critical', color: 'var(--critical)' },
  high: { label: 'High', rank: 3, text: 'text-high', bg: 'bg-high', soft: 'bg-high-soft', hl: 'hl-high', color: 'var(--high)' },
  medium: { label: 'Caution', rank: 2, text: 'text-caution', bg: 'bg-caution', soft: 'bg-caution-soft', hl: 'hl-medium', color: 'var(--caution)' },
  low: { label: 'Low', rank: 1, text: 'text-info', bg: 'bg-info', soft: 'bg-info-soft', hl: 'hl-low', color: 'var(--info)' },
  info: { label: 'Info', rank: 0, text: 'text-info', bg: 'bg-info', soft: 'bg-info-soft', hl: 'hl-info', color: 'var(--info)' },
}

export const FAVORABLE = { label: 'Favorable', text: 'text-ok', bg: 'bg-ok', soft: 'bg-ok-soft', hl: 'hl-favorable', color: 'var(--ok)' }

export const severityMeta = (finding) => (finding?.favorable ? FAVORABLE : SEVERITY[finding?.severity] || SEVERITY.info)

export const RISK_LEVEL = {
  low: { label: 'Low risk', tone: 'ok' },
  moderate: { label: 'Moderate risk', tone: 'caution' },
  elevated: { label: 'Elevated risk', tone: 'caution' },
  high: { label: 'High risk', tone: 'high' },
  severe: { label: 'Severe risk', tone: 'critical' },
}

export const TONE = {
  ok: { text: 'text-ok', bg: 'bg-ok', soft: 'bg-ok-soft', color: 'var(--ok)' },
  caution: { text: 'text-caution', bg: 'bg-caution', soft: 'bg-caution-soft', color: 'var(--caution)' },
  high: { text: 'text-high', bg: 'bg-high', soft: 'bg-high-soft', color: 'var(--high)' },
  critical: { text: 'text-critical', bg: 'bg-critical', soft: 'bg-critical-soft', color: 'var(--critical)' },
}

export const gradeTone = (grade) => ({ A: 'ok', B: 'ok', C: 'caution', D: 'high', F: 'critical' })[grade] || 'caution'

export const scoreTone = (score) => (score >= 80 ? 'ok' : score >= 60 ? 'caution' : score >= 40 ? 'high' : 'critical')

export const SOURCE_LABEL = { rule: 'Playbook rule', playbook: 'Playbook', embedding: 'Embeddings', llm: 'AI reasoning' }

export function bySeverity(a, b) {
  return (SEVERITY[b.severity]?.rank ?? 0) - (SEVERITY[a.severity]?.rank ?? 0) || b.score_impact - a.score_impact
}

export function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function relativeTime(iso) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`
  return formatDate(iso).split(',')[0]
}

export function pluralize(n, word, plural = `${word}s`) {
  return `${n} ${n === 1 ? word : plural}`
}
