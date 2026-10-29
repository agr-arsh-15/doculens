import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  BadgeAlert, ClipboardPaste, EyeOff, FileSearch, FileUp, Gauge, Layers, ListX, ScanLine, ShieldCheck,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Callout, Card, Chip, cx, Spinner } from '../components/ui'
import { api } from '../lib/api'

const ACCEPT = '.pdf,.docx,.txt,.md'

function DropZone({ onFile, busy }) {
  const input = useRef(null)
  const [over, setOver] = useState(false)
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        const file = e.dataTransfer.files?.[0]
        if (file) onFile(file)
      }}
      onClick={() => !busy && input.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
      className={cx(
        'group relative flex min-h-[260px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-8 py-10 text-center transition-all',
        over ? 'border-ink bg-surface-2 scale-[1.01]' : 'border-line-strong bg-surface hover:border-ink-2 hover:bg-surface-2',
      )}
      data-testid="dropzone"
    >
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="hidden"
        data-testid="file-input"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onFile(file)
          e.target.value = ''
        }}
      />
      {busy ? (
        <>
          <Spinner className="size-9 text-ink" />
          <div className="mt-4 font-serif text-xl font-semibold">Reading your document...</div>
          <div className="mt-1 text-sm text-muted">Extracting text, segmenting clauses and detecting the document type.</div>
        </>
      ) : (
        <>
          <div className="relative mb-5">
            <div className="grid size-16 place-items-center rounded-2xl bg-ink text-paper shadow-card transition-transform group-hover:-translate-y-1">
              <FileUp className="size-7" />
            </div>
            <div className="absolute -right-3 -top-2 rotate-6 rounded-md bg-high px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
              X-Ray
            </div>
          </div>
          <div className="font-serif text-2xl font-semibold">Drop any contract, offer letter, T&amp;C or policy</div>
          <div className="mt-2 text-sm text-muted">
            PDF, DOCX or TXT, up to 15 MB. <span className="font-medium text-ink underline underline-offset-4">Browse files</span>
          </div>
        </>
      )}
    </div>
  )
}

function PasteBox({ onSubmit, busy }) {
  const [text, setText] = useState('')
  const [name, setName] = useState('')
  const words = text.trim() ? text.trim().split(/\s+/).length : 0
  return (
    <div className="rounded-2xl border border-line bg-surface p-4">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name (optional), e.g. Acme offer letter"
        className="mb-3 h-10 w-full rounded-lg border border-line bg-surface-2 px-3 text-sm outline-none focus:border-accent"
      />
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste the full text of the document here..."
        className="scrollbar-thin h-56 w-full resize-none rounded-lg border border-line bg-surface-2 p-3 font-serif text-[15px] leading-relaxed outline-none focus:border-accent"
        data-testid="paste-textarea"
      />
      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-muted">{words.toLocaleString()} words</span>
        <Button variant="primary" loading={busy} disabled={words < 15} onClick={() => onSubmit(text, name || 'pasted-text')} icon={ScanLine}>
          Analyze text
        </Button>
      </div>
    </div>
  )
}

const CATCHES = [
  {
    icon: BadgeAlert, tone: 'critical', title: 'Risky clauses',
    body: 'One-sided indemnities, uncapped liability, forced arbitration, unilateral changes.',
    sample: <>The Company may <mark className="hl hl-critical">terminate immediately without notice</mark> or pay.</>,
  },
  {
    icon: EyeOff, tone: 'high', title: 'Hidden traps',
    body: 'Bonds buried under "Joining Formalities", terms that change "from time to time", missing annexures.',
    sample: <>Joining Formalities: <mark className="hl hl-high hl-hidden">originals retained for the bond period</mark>.</>,
  },
  {
    icon: ListX, tone: 'caution', title: 'Missing protections',
    body: 'Expected clauses for this document type that simply are not there.',
    sample: <>No <span className="rounded bg-caution-soft px-1 font-medium text-caution">breach notification</span> clause found.</>,
  },
  {
    icon: Gauge, tone: 'ok', title: 'Off-market terms',
    body: 'Notice periods, non-competes, liability caps and SLAs measured against market ranges.',
    sample: <>Non-compete <b>24 months</b> vs market <b>0 to 12 months</b>.</>,
  },
]

const STEPS = [
  { icon: FileSearch, title: 'Parse & segment', body: 'PDF, DOCX or text is split into numbered clauses with exact character offsets.' },
  { icon: Layers, title: 'Classify & map', body: 'Embeddings detect the document type, jurisdiction and parties, then map clauses to a playbook.' },
  { icon: ShieldCheck, title: 'Reason & verify', body: 'Playbook rules and AI reasoning flag risks; every quote is verified against the source text.' },
  { icon: Gauge, title: 'Score & benchmark', body: 'Values are compared with market ranges and rolled into a transparent, perspective-aware score.' },
]

export default function Landing() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('file')
  const goAnalyze = (doc) => navigate(`/analyze/${doc.id}`)

  const upload = useMutation({ mutationFn: api.uploadDocument, onSuccess: goAnalyze })
  const paste = useMutation({ mutationFn: ({ text, name }) => api.createTextDocument(text, name), onSuccess: goAnalyze })
  const error = upload.error || paste.error

  return (
    <div className="paper-grain">
      <section className="mx-auto grid max-w-[1200px] gap-10 px-5 pb-12 pt-12 lg:grid-cols-[1fr_1.05fr] lg:pt-20">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Chip className="mb-5" icon={ScanLine}>Contract risk analysis, explained</Chip>
          <h1 className="font-serif text-[44px] font-bold leading-[1.05] tracking-tight sm:text-[56px]">
            Read the fine print <span className="italic text-high">before</span> you sign it.
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-2">
            DocuLens X-rays offer letters, contracts, terms of service and compliance documents. It highlights risky, hidden and missing
            clauses, compares the numbers with market standards, and tells you exactly what to negotiate.
          </p>
          <div className="mt-8 grid max-w-xl grid-cols-3 gap-3 text-sm">
            {[
              ['8', 'document playbooks'],
              ['IN / US / EU', 'jurisdiction rules'],
              ['100%', 'quotes verified in source'],
            ].map(([k, v]) => (
              <div key={v} className="rounded-xl border border-line bg-surface/70 px-3 py-3">
                <div className="font-serif text-xl font-bold">{k}</div>
                <div className="text-xs text-muted">{v}</div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
          <div className="mb-3 flex items-center gap-1 rounded-xl bg-sunken/70 p-1 text-sm">
            {[
              ['file', 'Upload file', FileUp],
              ['text', 'Paste text', ClipboardPaste],
            ].map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setMode(key)}
                className={cx(
                  'flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg py-2 font-medium transition-colors',
                  mode === key ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink',
                )}
              >
                <Icon className="size-4" />
                {label}
              </button>
            ))}
          </div>
          {mode === 'file' ? (
            <DropZone onFile={(f) => upload.mutate(f)} busy={upload.isPending} />
          ) : (
            <PasteBox onSubmit={(text, name) => paste.mutate({ text, name })} busy={paste.isPending} />
          )}
          {error && (
            <Callout tone="error" className="mt-3" title="Could not read that document">
              {error.message}
            </Callout>
          )}
          <p className="mt-3 text-xs text-muted">
            Documents are processed by your own DocuLens server. With an LLM key configured, personal identifiers are redacted before any AI call.
          </p>
        </motion.div>
      </section>

      <section className="border-y border-line bg-surface/60">
        <div className="mx-auto max-w-[1200px] px-5 py-14">
          <h2 className="font-serif text-2xl font-semibold">What DocuLens catches</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {CATCHES.map(({ icon: Icon, title, body, sample: s, tone }) => (
              <Card key={title} className="p-5">
                <div className={cx('mb-3 grid size-9 place-items-center rounded-xl', `bg-${tone}-soft text-${tone}`)}>
                  <Icon className="size-[18px]" />
                </div>
                <div className="font-semibold">{title}</div>
                <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
                <div className="mt-4 rounded-lg border border-line bg-surface-2 px-3 py-2.5 font-serif text-[14px] leading-relaxed">{s}</div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1200px] px-5 py-14">
        <h2 className="font-serif text-2xl font-semibold">How it works</h2>
        <ol className="mt-6 grid gap-4 md:grid-cols-4">
          {STEPS.map(({ icon: Icon, title, body }, i) => (
            <li key={title} className="relative rounded-2xl border border-line bg-surface p-5">
              <div className="mb-3 flex items-center gap-3">
                <span className="font-mono text-xs text-faint">0{i + 1}</span>
                <Icon className="size-[18px] text-ink-2" />
              </div>
              <div className="font-semibold">{title}</div>
              <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
