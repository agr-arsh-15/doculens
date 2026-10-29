import { EyeOff } from 'lucide-react'
import { forwardRef, memo, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { severityMeta } from '../../lib/format'
import { clauseBodyStart, segmentRange, worstFinding } from '../../lib/highlights'
import { cx, Tooltip } from '../ui'

const Clause = memo(function Clause({ clause, text, findings, activeId, onSelect }) {
  const bodyStart = clauseBodyStart(clause, text)
  const segments = useMemo(() => segmentRange(text, bodyStart, clause.end, findings), [text, bodyStart, clause.end, findings])
  const risky = findings.filter((f) => !f.favorable)
  const worst = risky.length ? worstFinding(risky) : null
  const hidden = risky.some((f) => f.kind === 'hidden')
  const buried = risky.some((f) => f.buried)
  const headingText = bodyStart > clause.start ? text.slice(clause.start, bodyStart).trim() : null
  const meta = worst ? severityMeta(worst) : null

  return (
    <section
      id={`clause-${clause.id}`}
      data-clause={clause.id}
      className={cx(
        'relative scroll-mt-6 rounded-lg py-2 pl-5 pr-3 transition-colors',
        hidden && 'outline-1 outline-dashed outline-offset-2 outline-line-strong',
      )}
    >
      <span
        className="absolute bottom-2 left-0 top-2 w-[3px] rounded-full"
        style={{ background: meta ? meta.color : 'transparent', opacity: meta ? 0.85 : 0 }}
      />
      {(buried || hidden) && (
        <Tooltip content={risky.find((f) => f.hidden_reason)?.hidden_reason || 'Contains a risk that is easy to miss.'}>
          <span className="absolute -top-2 right-2 inline-flex cursor-help items-center gap-1 rounded-full border border-line-strong bg-surface px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-2">
            <EyeOff className="size-3" /> {buried ? 'Buried' : 'Hidden'}
          </span>
        </Tooltip>
      )}
      {headingText && <h3 className="mb-1 font-serif text-[17px] font-semibold leading-snug text-ink">{headingText}</h3>}
      <div className="whitespace-pre-wrap font-serif text-[16.5px] leading-[1.75] text-ink-2">
        {segments.map((seg, i) => {
          if (!seg.findings.length) return <span key={i}>{seg.text}</span>
          const top = seg.findings[0]
          const m = severityMeta(top)
          const active = seg.findings.some((f) => f.id === activeId)
          return (
            <mark
              key={i}
              data-fid={seg.findings.map((f) => f.id).join(' ')}
              onClick={(e) => {
                e.stopPropagation()
                const idx = seg.findings.findIndex((f) => f.id === activeId)
                onSelect(seg.findings[(idx + 1) % seg.findings.length].id, 'doc')
              }}
              title={seg.findings.map((f) => f.title).join(' | ')}
              className={cx('hl text-inherit', m.hl, top.kind === 'hidden' && 'hl-hidden', active && 'hl-active')}
            >
              {seg.text}
            </mark>
          )
        })}
      </div>
    </section>
  )
})

function HeatStrip({ markers, viewport, onJump }) {
  return (
    <div
      className="relative h-full w-3.5 shrink-0 cursor-pointer rounded-full bg-sunken/80"
      onClick={(e) => {
        const rect = e.currentTarget.getBoundingClientRect()
        onJump((e.clientY - rect.top) / rect.height)
      }}
      aria-label="Risk heat strip"
      data-testid="heat-strip"
    >
      <div className="absolute inset-x-0 rounded-full bg-ink/10 dark:bg-white/10" style={{ top: `${viewport.top * 100}%`, height: `${Math.max(4, viewport.height * 100)}%` }} />
      {markers.map((m) => (
        <Tooltip key={m.id} content={m.title} side="right">
          <span
            onClick={(e) => {
              e.stopPropagation()
              m.onClick()
            }}
            className="absolute left-1/2 -translate-x-1/2 rounded-full ring-2 ring-paper transition-transform hover:scale-125"
            style={{ top: `${m.top * 100}%`, width: m.size, height: `max(${m.size}px, ${m.height * 100}%)`, background: m.color }}
          />
        </Tooltip>
      ))}
    </div>
  )
}

const DocumentViewer = forwardRef(function DocumentViewer({ text, clauses, findings, activeId, onSelect }, ref) {
  const scroller = useRef(null)
  const [markers, setMarkers] = useState([])
  const [viewport, setViewport] = useState({ top: 0, height: 1 })

  const byClause = useMemo(() => {
    const map = {}
    for (const f of findings) {
      if (f.kind === 'missing') continue
      const ids = new Set(f.clause_ids || [])
      for (const c of clauses) {
        if (f.quote_start != null && f.quote_start < c.end && f.quote_end > c.start) ids.add(c.id)
      }
      ids.forEach((id) => (map[id] = map[id] || []).push(f))
    }
    return map
  }, [findings, clauses])

  const scrollToFinding = useCallback((fid) => {
    const root = scroller.current
    if (!root) return
    const f = findings.find((x) => x.id === fid)
    const el = root.querySelector(`mark[data-fid~="${fid}"]`) || (f?.clause_ids?.[0] && root.querySelector(`#clause-${f.clause_ids[0]}`))
    if (!el) return
    const top = el.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop - root.clientHeight / 3
    root.scrollTo({ top, behavior: 'smooth' })
    const clauseEl = el.closest('section') || el
    clauseEl.classList.remove('flash')
    void clauseEl.offsetWidth
    clauseEl.classList.add('flash')
  }, [findings])

  const scrollToClause = useCallback((cid) => {
    const root = scroller.current
    const el = root?.querySelector(`#clause-${cid}`)
    if (!el) return
    root.scrollTo({ top: el.offsetTop - 24, behavior: 'smooth' })
    el.classList.remove('flash')
    void el.offsetWidth
    el.classList.add('flash')
  }, [])

  useImperativeHandle(ref, () => ({ scrollToFinding, scrollToClause }), [scrollToFinding, scrollToClause])

  const measure = useCallback(() => {
    const root = scroller.current
    if (!root || !root.scrollHeight) return
    const total = root.scrollHeight
    const list = []
    for (const c of clauses) {
      const fs = (byClause[c.id] || []).filter((f) => !f.favorable)
      if (!fs.length) continue
      const el = root.querySelector(`#clause-${c.id}`)
      if (!el) continue
      const worst = worstFinding(fs)
      const meta = severityMeta(worst)
      list.push({
        id: c.id,
        top: el.offsetTop / total,
        height: el.offsetHeight / total,
        size: worst.severity === 'critical' ? 10 : worst.severity === 'high' ? 9 : 7,
        color: meta.color,
        title: `${fs.length} finding${fs.length > 1 ? 's' : ''}: ${fs.map((f) => f.title).slice(0, 3).join('; ')}`,
        onClick: () => onSelect(worst.id, 'strip'),
      })
    }
    setMarkers(list)
    setViewport({ top: root.scrollTop / total, height: root.clientHeight / total })
  }, [clauses, byClause, onSelect])

  useLayoutEffect(() => {
    measure()
    const root = scroller.current
    const ro = new ResizeObserver(measure)
    if (root) ro.observe(root)
    return () => ro.disconnect()
  }, [measure])

  useEffect(() => {
    const root = scroller.current
    if (!root) return
    const onScroll = () => setViewport({ top: root.scrollTop / root.scrollHeight, height: root.clientHeight / root.scrollHeight })
    root.addEventListener('scroll', onScroll, { passive: true })
    return () => root.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="flex h-full gap-3">
      <HeatStrip
        markers={markers}
        viewport={viewport}
        onJump={(ratio) => scroller.current?.scrollTo({ top: ratio * scroller.current.scrollHeight - scroller.current.clientHeight / 2, behavior: 'smooth' })}
      />
      <div ref={scroller} className="scrollbar-thin relative h-full flex-1 overflow-y-auto rounded-2xl border border-line bg-surface shadow-card" data-testid="document-viewer">
        <article className="mx-auto max-w-[760px] space-y-1 px-6 py-8 sm:px-10">
          {clauses.map((c) => (
            <Clause key={c.id} clause={c} text={text} findings={byClause[c.id] || EMPTY} activeId={activeId} onSelect={onSelect} />
          ))}
        </article>
      </div>
    </div>
  )
})

const EMPTY = []

export default DocumentViewer
