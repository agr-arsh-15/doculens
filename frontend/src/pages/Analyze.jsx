import { useMutation, useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Building2, FileText, Globe2, Lock, ScanLine, Sparkles, User, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ProgressTracker from '../components/ProgressTracker'
import { Button, Callout, Card, Chip, cx, EmptyState, Select, Spinner, Switch, Tooltip } from '../components/ui'
import { api } from '../lib/api'

function Field({ label, hint, children }) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="text-[13px] font-semibold uppercase tracking-wide text-muted">{label}</span>
        {hint && <span className="text-xs text-faint">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function Outline({ clauses }) {
  const headed = clauses.filter((c) => c.heading || c.number)
  return (
    <Card className="p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="font-serif text-lg font-semibold">Document outline</h3>
        <span className="text-xs text-muted">{clauses.length} clauses detected</span>
      </div>
      <ol className="scrollbar-thin mt-3 max-h-[440px] space-y-0.5 overflow-y-auto pr-2 font-serif text-[15px]">
        {(headed.length ? headed : clauses).slice(0, 80).map((c) => (
          <li key={c.id} className="flex gap-3 rounded-md px-2 py-1 hover:bg-surface-2" style={{ paddingLeft: 8 + Math.min(c.level, 3) * 14 }}>
            <span className="w-8 shrink-0 font-mono text-xs leading-6 text-faint">{c.number || c.id}</span>
            <span className="truncate">{c.heading || c.text.slice(0, 80)}</span>
          </li>
        ))}
      </ol>
    </Card>
  )
}

export default function Analyze() {
  const { docId } = useParams()
  const navigate = useNavigate()
  const doc = useQuery({ queryKey: ['document', docId], queryFn: () => api.document(docId) })
  const playbooks = useQuery({ queryKey: ['playbooks'], queryFn: api.playbooks })
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta })
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })

  const det = doc.data?.detection
  const [docTypeChoice, setDocType] = useState(null)
  const [jurisdictionChoice, setJurisdiction] = useState(null)
  const [perspectiveChoice, setPerspective] = useState(null)
  const [useLlm, setUseLlm] = useState(true)
  const [privacy, setPrivacy] = useState(false)
  const [running, setRunning] = useState(null)

  const docType = docTypeChoice ?? det?.doc_type ?? null
  const jurisdiction = jurisdictionChoice ?? det?.jurisdiction ?? null
  const llmEnabled = !!health.data?.llm?.enabled
  const book = useMemo(() => playbooks.data?.find((p) => p.id === docType), [playbooks.data, docType])
  const perspective = useMemo(() => {
    if (!book) return perspectiveChoice ?? det?.default_perspective ?? null
    const ids = book.perspectives.map((p) => p.id)
    if (ids.includes(perspectiveChoice)) return perspectiveChoice
    if (ids.includes(det?.default_perspective)) return det.default_perspective
    return ids[0]
  }, [book, perspectiveChoice, det])

  const start = useMutation({
    mutationFn: (force) =>
      api.createAnalysis({ document_id: docId, doc_type: docType, jurisdiction, perspective, use_llm: useLlm && llmEnabled, privacy_mode: privacy, force }),
    onSuccess: (status) => {
      if (status.status === 'completed') navigate(`/report/${status.id}`, { replace: false })
      else setRunning(status.id)
    },
  })

  if (doc.isLoading) {
    return (
      <div className="grid min-h-[60vh] place-items-center">
        <Spinner className="size-6" />
      </div>
    )
  }
  if (doc.isError) {
    return (
      <EmptyState icon={FileText} title="Document not found" action={<Button as={Link} to="/">Upload a document</Button>}>
        {doc.error.message}
      </EmptyState>
    )
  }

  const d = doc.data
  const docTypeOptions = (playbooks.data || []).map((p) => ({ value: p.id, label: p.name }))
  const jurisdictionOptions = Object.entries(meta.data?.jurisdictions || { [det.jurisdiction]: det.jurisdiction_label }).map(([value, label]) => ({ value, label }))
  return (
    <div className="mx-auto max-w-[1200px] px-5 py-10">
      <div className="mb-6">
        <div className="text-sm text-muted">Step 2 of 3</div>
        <h1 className="font-serif text-3xl font-bold tracking-tight">Confirm what we found</h1>
        <p className="mt-1 text-ink-2">Check the detected details and tell us whose side you are on. Every finding is judged from that perspective.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <div className="space-y-6">
          {running ? (
            <ProgressTracker
              analysisId={running}
              useLlm={useLlm && llmEnabled}
              onDone={() => navigate(`/report/${running}`, { replace: true })}
              onRetry={() => {
                setRunning(null)
                start.mutate(true)
              }}
            />
          ) : (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <Card className="p-6">
                <div className="flex items-start gap-3 border-b border-line pb-5">
                  <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-sunken">
                    <FileText className="size-5 text-ink-2" />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-lg font-semibold" data-testid="doc-filename">{d.filename}</div>
                    <div className="mt-0.5 text-sm text-muted">
                      {d.source_type.toUpperCase()} · {d.page_count} {d.page_count === 1 ? 'page' : 'pages'} · {d.word_count.toLocaleString()} words
                      {d.ocr_used && ' · OCR'}
                    </div>
                  </div>
                </div>

                {d.warnings?.map((w) => (
                  <Callout key={w} tone="warning" className="mt-4">{w}</Callout>
                ))}

                <div className="mt-5 grid gap-5 sm:grid-cols-2">
                  <Field label="Document type" hint={`${Math.round(det.doc_type_confidence * 100)}% confident`}>
                    <Select value={docType || ''} onChange={setDocType} options={docTypeOptions} className="w-full" data-testid="doctype-select" />
                  </Field>
                  <Field label="Jurisdiction">
                    <Select value={jurisdiction || ''} onChange={setJurisdiction} options={jurisdictionOptions} className="w-full" />
                    {det.jurisdiction_evidence?.length > 0 && (
                      <Tooltip content={det.jurisdiction_evidence.join(' · ')}>
                        <div className="mt-2 inline-flex cursor-help items-center gap-1 text-xs text-muted">
                          <Globe2 className="size-3.5" /> Based on {det.jurisdiction_evidence.length} signal{det.jurisdiction_evidence.length > 1 ? 's' : ''}
                        </div>
                      </Tooltip>
                    )}
                  </Field>
                </div>

                {det.parties?.length > 0 && (
                  <div className="mt-5">
                    <Field label="Parties">
                      <div className="flex flex-wrap gap-2">
                        {det.parties.map((p) => (
                          <Chip key={p.name} icon={/limited|inc|llc|ltd|corp|company|pvt/i.test(p.name) ? Building2 : User} className="py-1">
                            {p.name.split(' ("')[0]}
                            {p.role && <span className="text-muted">· {p.role}</span>}
                          </Chip>
                        ))}
                      </div>
                    </Field>
                  </div>
                )}

                <div className="mt-6">
                  <Field label="I am reading this as the">
                    <div className="grid gap-2 sm:grid-cols-2" role="radiogroup">
                      {(book?.perspectives || det.perspectives).map((p) => (
                        <button
                          key={p.id}
                          role="radio"
                          aria-checked={perspective === p.id}
                          onClick={() => setPerspective(p.id)}
                          data-testid={`perspective-${p.id}`}
                          className={cx(
                            'flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 text-left transition-all',
                            perspective === p.id ? 'border-ink bg-surface-2 ring-1 ring-ink' : 'border-line hover:border-line-strong',
                          )}
                        >
                          <span className={cx('mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border-2', perspective === p.id ? 'border-ink' : 'border-line-strong')}>
                            {perspective === p.id && <span className="size-1.5 rounded-full bg-ink" />}
                          </span>
                          <span>
                            <span className="block font-semibold">{p.label}</span>
                            {p.description && <span className="mt-0.5 block text-xs leading-relaxed text-muted">{p.description}</span>}
                          </span>
                        </button>
                      ))}
                    </div>
                  </Field>
                </div>

                <div className="mt-6 space-y-3 rounded-xl bg-surface-2 p-4">
                  <label className="flex items-center justify-between gap-4">
                    <span>
                      <span className="flex items-center gap-2 text-sm font-semibold">
                        <Sparkles className="size-4" /> AI clause reasoning
                      </span>
                      <span className="block text-xs text-muted">
                        {llmEnabled
                          ? `Uses ${health.data.llm.provider} (${health.data.llm.model}) on top of playbook rules. Quotes are verified against the source.`
                          : 'No LLM key configured. Runs in local mode (rules + embeddings). Add GROQ_API_KEY or GEMINI_API_KEY to .env for deeper analysis.'}
                      </span>
                    </span>
                    <Switch checked={useLlm && llmEnabled} onCheckedChange={setUseLlm} disabled={!llmEnabled} />
                  </label>
                  <label className="flex items-center justify-between gap-4">
                    <span>
                      <span className="flex items-center gap-2 text-sm font-semibold">
                        <Lock className="size-4" /> Strict privacy mode
                      </span>
                      <span className="block text-xs text-muted">Also redacts party names and money amounts before AI calls. IDs, emails and phone numbers are always redacted.</span>
                    </span>
                    <Switch checked={privacy} onCheckedChange={setPrivacy} disabled={!llmEnabled || !useLlm} />
                  </label>
                </div>

                {start.isError && <Callout tone="error" className="mt-4">{start.error.message}</Callout>}

                <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
                  <Link to="/" className="text-sm text-muted hover:text-ink">Use a different document</Link>
                  <Button variant="primary" size="lg" icon={ScanLine} loading={start.isPending} onClick={() => start.mutate(false)} data-testid="run-xray">
                    Run X-Ray
                  </Button>
                </div>
              </Card>
            </motion.div>
          )}
        </div>

        <div className="space-y-6">
          <Outline clauses={d.clauses} />
          {book && (
            <Card className="p-5">
              <div className="flex items-center gap-2">
                <Users className="size-4 text-muted" />
                <h3 className="font-semibold">{book.name} playbook</h3>
                <span className="ml-auto font-mono text-xs text-faint">v{book.version}</span>
              </div>
              <p className="mt-1 text-sm text-muted">
                Checks {book.clauses.length} clause types and {book.red_flag_count} red-flag patterns against market standards.
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {book.clauses.map((c) => (
                  <Chip key={c.id} solid={c.importance === 'critical'}>{c.label}</Chip>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
