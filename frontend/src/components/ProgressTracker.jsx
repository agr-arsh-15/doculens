import { motion } from 'framer-motion'
import { Check, Circle, Loader2, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Button, Callout, Card, cx } from './ui'

const BASE_STAGES = [
  ['parsing', 'Parsing document'],
  ['segmenting', 'Segmenting clauses'],
  ['classifying', 'Classifying type, jurisdiction and parties'],
  ['mapping', 'Mapping clauses to the playbook'],
  ['rules', 'Running playbook rules'],
  ['reasoning', 'AI clause reasoning'],
  ['verifying', 'Verifying evidence quotes'],
  ['hidden', 'Hunting for hidden risks'],
  ['benchmarking', 'Comparing against market standards'],
  ['scoring', 'Scoring and summarizing'],
]

export default function ProgressTracker({ analysisId, useLlm, onDone, onRetry }) {
  const stages = BASE_STAGES.filter(([k]) => useLlm || (k !== 'reasoning' && k !== 'verifying'))
  const [current, setCurrent] = useState({ stage: 'queued', label: 'Queued', progress: 1 })
  const [failed, setFailed] = useState(null)
  const seen = useRef(new Set())
  const doneRef = useRef(onDone)
  useEffect(() => {
    doneRef.current = onDone
  }, [onDone])

  useEffect(() => {
    let closed = false
    const es = new EventSource(api.eventsUrl(analysisId))
    es.onmessage = (msg) => {
      const event = JSON.parse(msg.data)
      seen.current.add(event.stage)
      setCurrent(event)
      if (event.status === 'completed') {
        closed = true
        es.close()
        setTimeout(() => doneRef.current?.(), 450)
      } else if (event.status === 'failed') {
        closed = true
        es.close()
        setFailed(event.label)
      }
    }
    es.onerror = () => {
      if (closed) return
      es.close()
      api.analysisStatus(analysisId)
        .then((s) => (s.status === 'completed' ? doneRef.current?.() : setFailed(s.error || 'Lost connection to the analysis stream.')))
        .catch((e) => setFailed(e.message))
    }
    return () => {
      closed = true
      es.close()
    }
  }, [analysisId])

  const order = stages.map(([k]) => k)
  const activeIndex = current.stage === 'done' ? order.length : Math.max(0, order.indexOf(current.stage))

  return (
    <Card className="p-6" data-testid="progress-tracker">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="font-serif text-2xl font-semibold">Running the X-Ray</h2>
        <span className="font-mono text-sm text-muted">{current.progress}%</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-line">
        <motion.div
          className={cx('h-full rounded-full', failed ? 'bg-critical' : 'bg-ink')}
          animate={{ width: `${current.progress}%` }}
          transition={{ type: 'spring', stiffness: 60, damping: 18 }}
        />
      </div>
      <p className="mt-2 text-sm text-muted">{failed ? 'The analysis stopped.' : current.label}</p>

      <ol className="mt-6 space-y-1">
        {stages.map(([key, label], i) => {
          const state = failed && i === activeIndex ? 'failed' : i < activeIndex ? 'done' : i === activeIndex ? 'active' : 'pending'
          return (
            <li key={key} className={cx('flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm', state === 'active' && 'bg-surface-2')}>
              <span className="grid size-6 place-items-center">
                {state === 'done' && <Check className="size-4 text-ok" />}
                {state === 'active' && <Loader2 className="size-4 animate-spin text-ink" />}
                {state === 'pending' && <Circle className="size-3 text-line-strong" />}
                {state === 'failed' && <XCircle className="size-4 text-critical" />}
              </span>
              <span className={cx(state === 'pending' ? 'text-faint' : 'text-ink', state === 'active' && 'font-medium')}>
                {state === 'active' && key === 'reasoning' ? current.label : label}
              </span>
            </li>
          )
        })}
      </ol>

      {failed && (
        <Callout tone="error" className="mt-5" title="Analysis failed" action={<Button size="sm" onClick={onRetry}>Try again</Button>}>
          {failed}
        </Callout>
      )}
    </Card>
  )
}
