import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Binary, Boxes, BrainCircuit, Scissors } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from 'recharts'
import { Button, Card, Chip, cx, EmptyState, Meter, Spinner } from '../components/ui'
import { api } from '../lib/api'

const LAYERS = [
  { key: 'layer1', icon: Scissors, title: 'Preprocessing', sub: 'Sentence segmentation, tokenization, stop words, POS tags, lemmas' },
  { key: 'layer2', icon: Binary, title: 'Features', sub: 'TF-IDF, n-grams, readability, lexicon tone' },
  { key: 'layer3', icon: Boxes, title: 'Extraction', sub: 'Doc-type classification, values, parties, clause mapping' },
  { key: 'layer4', icon: BrainCircuit, title: 'Understanding', sub: 'TextRank, obligations, AI reasoning and verification' },
]

const tooltipStyle = { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 12, color: 'var(--ink)' }

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-line bg-surface-2 px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 font-serif text-2xl font-bold tabular-nums">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  )
}

function Panel({ title, children, className, aside }) {
  return (
    <Card className={cx('p-5', className)}>
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="font-semibold">{title}</h3>
        {aside && <span className="text-xs text-muted">{aside}</span>}
      </div>
      {children}
    </Card>
  )
}

function HBars({ data, valueKey, labelKey, color = 'var(--accent)', height }) {
  return (
    <ResponsiveContainer width="100%" height={height || Math.max(160, data.length * 26)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 0, bottom: 0 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey={labelKey} width={150} tick={{ fill: 'var(--ink-2)', fontSize: 12 }} axisLine={false} tickLine={false} />
        <RTooltip contentStyle={tooltipStyle} cursor={{ fill: 'var(--sunken)' }} />
        <Bar dataKey={valueKey} fill={color} radius={[0, 4, 4, 0]} barSize={14} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function Layer1({ l }) {
  const pos = Object.entries(l.pos_distribution).map(([name, value]) => ({ name, value }))
  const kept = l.raw_word_count - l.stop_words_removed_count
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Characters" value={l.total_characters.toLocaleString()} />
        <Stat label="Tokens" value={l.raw_word_count.toLocaleString()} />
        <Stat label="Sentences" value={l.sentence_count} sub={`via ${l.sentence_tokenizer}`} />
        <Stat label="Vocabulary" value={l.vocabulary_size.toLocaleString()} sub="unique content words" />
        <Stat label="Noise removed" value={`${l.token_reduction_percent}%`} sub={`${l.stop_words_removed_count.toLocaleString()} stop words`} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Token funnel" aside={`${l.execution_time_ms} ms`}>
          <div className="space-y-3 text-sm">
            {[
              ['Raw tokens', l.raw_word_count],
              ['After stop-word and noise removal', kept],
              ['Unique vocabulary', l.vocabulary_size],
            ].map(([label, v]) => (
              <div key={label}>
                <div className="mb-1 flex justify-between"><span className="text-ink-2">{label}</span><span className="font-mono text-xs">{v.toLocaleString()}</span></div>
                <Meter value={v} max={l.raw_word_count || 1} tone="ok" />
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Part-of-speech distribution">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={pos}>
              <XAxis dataKey="name" tick={{ fill: 'var(--ink-2)', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <RTooltip contentStyle={tooltipStyle} cursor={{ fill: 'var(--sunken)' }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {pos.map((_, i) => <Cell key={i} fill={['var(--accent)', 'var(--high)', 'var(--caution)', 'var(--ok)', 'var(--faint)'][i % 5]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Sentence segmentation (first 5)">
          <ol className="space-y-2">
            {l.sample_sentences.map((s, i) => (
              <li key={i} className="flex gap-3 font-serif text-[14px] leading-relaxed">
                <span className="font-mono text-xs leading-6 text-faint">S{i + 1}</span>
                <span className="line-clamp-3">{s}</span>
              </li>
            ))}
          </ol>
        </Panel>
        <Panel title={`Lemmatization samples · ${l.lemmatizer || 'WordNet'}`}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
            {l.sample_lemmas.map((s) => (
              <div key={s.word} className="flex items-center gap-2 font-mono text-[12.5px]">
                <span className="text-ink-2">{s.word}</span>
                <span className="text-faint">→</span>
                <span className="font-semibold">{s.lemma}</span>
                <span className="ml-auto text-[10px] uppercase text-muted">{s.pos}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}

function Layer2({ l }) {
  const [n, setN] = useState('bigrams')
  const r = l.readability
  const s = l.sentiment
  const grams = l[n]
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Flesch ease" value={r.flesch_reading_ease} sub={r.complexity_level} />
        <Stat label="FK grade" value={r.flesch_kincaid_grade} sub="US school grade" />
        <Stat label="Gunning fog" value={r.gunning_fog_index} />
        <Stat label="Words / sentence" value={r.avg_words_per_sentence} />
        <Stat label="Read time" value={`${r.estimated_read_time_minutes} min`} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="TF-IDF keywords" aside={`${l.execution_time_ms} ms`}>
          <HBars data={l.tfidf_top_keywords.slice(0, 12)} valueKey="score" labelKey="term" />
        </Panel>
        <Panel
          title="N-gram frequencies"
          aside={
            <span className="inline-flex gap-1">
              {['unigrams', 'bigrams', 'trigrams'].map((k) => (
                <button key={k} onClick={() => setN(k)} className={cx('cursor-pointer rounded px-1.5 py-0.5', n === k ? 'bg-ink text-paper' : 'hover:text-ink')}>{k}</button>
              ))}
            </span>
          }
        >
          <HBars data={grams.slice(0, 10)} valueKey="frequency" labelKey="ngram" color="var(--high)" />
        </Panel>
      </div>
      <Panel title="Lexicon tone (VADER-style)" aside={s.tone_label}>
        <div className="relative mt-2 h-3 rounded-full" style={{ background: 'linear-gradient(90deg, var(--critical), var(--caution), var(--ok))' }}>
          <div className="absolute top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-surface bg-ink shadow" style={{ left: `${((s.compound + 1) / 2) * 100}%` }} />
        </div>
        <div className="mt-2 flex justify-between text-[11px] text-muted"><span>Negative</span><span>compound {s.compound}</span><span>Positive</span></div>
        <p className="mt-3 text-sm text-ink-2">{s.tone_explanation}</p>
        <p className="mt-2 text-xs text-muted">Tone is a linguistic signal only. Risk is judged by the playbook and reasoning layers, not by sentiment.</p>
      </Panel>
    </div>
  )
}

function Layer3({ l }) {
  const cands = l.doc_type_candidates.map((o) => {
    const [label, score] = Object.entries(o)[0]
    return { label, score }
  })
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Clauses" value={l.clause_count} sub={`${l.typed_clause_count} mapped to playbook types`} />
        <Stat label="Durations" value={l.value_counts.duration} />
        <Stat label="Money amounts" value={l.value_counts.money} />
        <Stat label="Embeddings" value={l.embedding_backend.startsWith('neural') ? 'Neural' : 'TF-IDF'} sub={l.embedding_backend.replace('neural:', '')} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Document-type classification" aside="0.45 title + 0.35 embedding + 0.20 keyword coverage">
          <HBars data={cands} valueKey="score" labelKey="label" height={170} />
        </Panel>
        <Panel title="Jurisdiction and parties">
          <ul className="space-y-1 text-sm">
            {l.jurisdiction_evidence.map((e) => <li key={e} className="font-mono text-xs text-ink-2">{e}</li>)}
          </ul>
          <div className="mt-4 flex flex-wrap gap-2">
            {l.parties.map((p) => <Chip key={p.name}>{p.name.split(' ("')[0]}{p.role && <span className="text-muted">· {p.role}</span>}</Chip>)}
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            {Object.entries(l.findings_by_source).map(([k, v]) => <Chip key={k}>{k}: {v}</Chip>)}
            {Object.entries(l.findings_by_kind).map(([k, v]) => <Chip key={k} className="bg-accent-soft text-accent">{k}: {v}</Chip>)}
          </div>
        </Panel>
      </div>
      <Panel title="Extracted values (pattern-based NER)">
        <div className="flex flex-wrap gap-2">
          {l.values.map((v, i) => (
            <span key={i} className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface-2 px-2.5 py-1 text-xs">
              <span className="font-semibold uppercase text-muted">{v.kind}</span>
              <span className="font-serif">{v.text}</span>
              <span className="font-mono text-accent">{v.normalized}</span>
            </span>
          ))}
        </div>
      </Panel>
      <Panel title="Clause-type mapping" aside="0.55 embedding similarity + 0.45 keyword score, threshold 0.42">
        <div className="scrollbar-thin max-h-[420px] overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-surface text-[11px] uppercase tracking-wide text-muted">
              <tr><th className="py-2 pr-3">Clause</th><th className="py-2 pr-3">Top candidate types</th><th className="py-2">Assigned</th></tr>
            </thead>
            <tbody>
              {l.classifications.map((c) => (
                <tr key={c.clause_id} className="border-t border-line align-top">
                  <td className="py-2 pr-3"><span className="font-mono text-xs text-faint">{c.clause_id}</span> <span className="ml-1">{c.label}</span></td>
                  <td className="py-2 pr-3 font-mono text-xs text-muted">
                    {c.top_types.map((t) => Object.entries(t)[0]).map(([k, v]) => `${k} ${v.toFixed(2)}`).join(' · ')}
                  </td>
                  <td className="py-2">{c.assigned.map((a) => <Chip key={a} className="mr-1">{a}</Chip>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

function Layer4({ l }) {
  const timings = Object.entries(l.stage_timings_ms).map(([stage, ms]) => ({ stage, ms }))
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Engine mode" value={l.engine_mode === 'hybrid' ? 'Hybrid' : 'Local'} sub={l.llm_provider} />
        <Stat label="AI batches" value={l.llm_batches} />
        <Stat label="AI findings proposed" value={l.llm_findings_proposed} sub={`${l.llm_findings_rejected_unverified} rejected (unverifiable quote)`} />
        <Stat label="Verified findings" value={l.verified_findings} />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="TextRank extractive summary" aside="graph centrality over sentence similarity">
          <ol className="list-decimal space-y-2 pl-5 font-serif text-[14px] leading-relaxed">
            {l.textrank_summary.map((s, i) => <li key={i} className="line-clamp-4">{s}</li>)}
          </ol>
        </Panel>
        <Panel title="Risk summary" aside={l.summary_source === 'llm' ? 'LLM-written' : 'template'}>
          <p className="font-serif text-[15px] leading-relaxed">{l.summary}</p>
        </Panel>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Obligation sentences (modal-verb detection)">
          <ul className="space-y-2 text-sm">
            {l.obligations.map((o, i) => <li key={i} className="border-l-2 border-accent/40 pl-3 font-serif leading-relaxed">{o}</li>)}
          </ul>
        </Panel>
        <Panel title="Stage timings (ms)">
          <HBars data={timings} valueKey="ms" labelKey="stage" color="var(--ok)" height={200} />
        </Panel>
      </div>
    </div>
  )
}

export default function Lab() {
  const { id } = useParams()
  const lab = useQuery({ queryKey: ['lab', id], queryFn: () => api.lab(id), staleTime: Infinity })
  const [layer, setLayer] = useState('layer1')

  return (
    <div className="mx-auto max-w-[1300px] px-5 py-8">
      <Link to={`/report/${id}`} className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> Back to report
      </Link>
      <h1 className="font-serif text-3xl font-bold tracking-tight">NLP Lab: under the hood</h1>
      <p className="mt-1 max-w-3xl text-ink-2">
        The four classic NLP layers behind this analysis. The product view uses the playbook, embedding and reasoning layers; this view exposes
        every intermediate step for study and demonstration.
      </p>

      <div className="mt-6 grid gap-3 md:grid-cols-4">
        {LAYERS.map(({ key, icon: Icon, title, sub }, i) => (
          <button
            key={key}
            onClick={() => setLayer(key)}
            className={cx(
              'relative cursor-pointer rounded-2xl border p-4 text-left transition-all',
              layer === key ? 'border-ink bg-surface shadow-card ring-1 ring-ink' : 'border-line bg-surface/60 hover:border-line-strong',
            )}
          >
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-faint">L{i + 1}</span>
              <Icon className="size-4" />
              <span className="font-semibold">{title}</span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-muted">{sub}</p>
          </button>
        ))}
      </div>

      <div className="mt-6">
        {lab.isLoading && <div className="grid h-64 place-items-center"><Spinner className="size-6" /></div>}
        {lab.isError && (
          <EmptyState icon={BrainCircuit} title="Lab unavailable" action={<Button as={Link} to="/history">Open history</Button>}>
            {lab.error.message}
          </EmptyState>
        )}
        {lab.data && (
          <>
            {layer === 'layer1' && <Layer1 l={lab.data.layer1} />}
            {layer === 'layer2' && <Layer2 l={lab.data.layer2} />}
            {layer === 'layer3' && <Layer3 l={lab.data.layer3} />}
            {layer === 'layer4' && <Layer4 l={lab.data.layer4} />}
          </>
        )}
      </div>
    </div>
  )
}
