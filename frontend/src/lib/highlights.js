import { SEVERITY } from './format'

const priority = (f) => (f.favorable ? 0 : 10 + (SEVERITY[f.severity]?.rank ?? 0))

/** Split [start, end) of the document into plain and highlighted segments; overlaps resolve to the most severe finding. */
export function segmentRange(text, start, end, findings) {
  const spans = findings
    .filter((f) => f.quote_start != null && f.quote_end != null && f.quote_end > start && f.quote_start < end)
    .map((f) => ({ s: Math.max(start, f.quote_start), e: Math.min(end, f.quote_end), f }))
  if (!spans.length) return [{ text: text.slice(start, end), findings: [] }]
  const cuts = new Set([start, end])
  spans.forEach(({ s, e }) => {
    cuts.add(s)
    cuts.add(e)
  })
  const points = [...cuts].sort((a, b) => a - b)
  const out = []
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i]
    const b = points[i + 1]
    if (a >= b) continue
    const covering = spans.filter(({ s, e }) => s <= a && e >= b).map(({ f }) => f).sort((x, y) => priority(y) - priority(x))
    const last = out[out.length - 1]
    const key = covering.map((f) => f.id).join(',')
    if (last && last.key === key) last.text += text.slice(a, b)
    else out.push({ text: text.slice(a, b), findings: covering, key })
  }
  return out
}

export function worstFinding(findings) {
  return [...findings].sort((x, y) => priority(y) - priority(x))[0]
}

/** Clause body without the heading line, so headings render separately. */
export function clauseBodyStart(clause, text) {
  if (!clause.heading) return clause.start
  const firstBreak = text.indexOf('\n', clause.start)
  if (firstBreak === -1 || firstBreak >= clause.end) return clause.start
  const firstLine = text.slice(clause.start, firstBreak).toLowerCase()
  return firstLine.includes(clause.heading.toLowerCase().slice(0, 24)) ? firstBreak + 1 : clause.start
}

export const normalizeForMatch = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
