import { useQuery } from '@tanstack/react-query'
import { Download, FileText, FlaskConical, GitCompareArrows, MessageSquareText, RefreshCw, ScrollText } from 'lucide-react'
import { lazy, Suspense, useCallback, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ChatDrawer from '../components/report/ChatDrawer'
import DocumentViewer from '../components/report/DocumentViewer'
import FindingsRail from '../components/report/FindingsRail'
import Scorecard from '../components/report/Scorecard'
import { Button, Callout, cx, EmptyState, Spinner } from '../components/ui'
import { api } from '../lib/api'

const PdfViewer = lazy(() => import('../components/report/PdfViewer'))

function tabFor(f) {
  if (f.favorable) return 'favorable'
  if (f.kind === 'missing') return 'missing'
  return 'risks'
}

export default function Report() {
  const { id } = useParams()
  const result = useQuery({ queryKey: ['analysis', id], queryFn: () => api.analysis(id), staleTime: Infinity })
  const docId = result.data?.document_id
  const doc = useQuery({ queryKey: ['document', docId], queryFn: () => api.document(docId), enabled: !!docId, staleTime: Infinity })

  const [activeId, setActiveId] = useState(null)
  const [tab, setTab] = useState('risks')
  const [view, setView] = useState('clauses')
  const [chatOpen, setChatOpen] = useState(false)
  const viewer = useRef(null)
  const findings = result.data?.findings

  const select = useCallback(
    (fid, from) => {
      setActiveId(fid)
      const f = findings?.find((x) => x.id === fid)
      if (!f) return
      if (from !== 'rail') setTab((t) => (t === 'hidden' && f.kind === 'hidden' ? t : tabFor(f)))
      if (from !== 'doc') {
        setView('clauses')
        setTimeout(() => viewer.current?.scrollToFinding(fid), 60)
      }
    },
    [findings],
  )

  if (result.isLoading) {
    return <div className="grid min-h-[60vh] place-items-center"><Spinner className="size-6" /></div>
  }
  if (result.isError) {
    return (
      <EmptyState icon={FileText} title={result.error.status === 409 ? 'Analysis not finished' : 'Report not found'} action={<Button as={Link} to="/history">Open history</Button>}>
        {result.error.message}
      </EmptyState>
    )
  }

  const r = result.data
  const d = doc.data
  const canPdf = d?.has_original_file && d?.source_type === 'pdf'

  return (
    <div className="mx-auto max-w-[1500px] px-5 py-6">
      <div className="no-print mb-4 flex flex-wrap items-center gap-2">
        <Button variant="primary" size="sm" icon={MessageSquareText} onClick={() => setChatOpen(true)} data-testid="open-chat">Ask the document</Button>
        <Button as="a" href={api.reportUrl(r.analysis_id)} download size="sm" icon={Download}>PDF report</Button>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button as={Link} to={`/lab/${r.analysis_id}`} size="sm" variant="ghost" icon={FlaskConical}>NLP Lab</Button>
          <Button as={Link} to={`/compare?a=${r.analysis_id}`} size="sm" variant="ghost" icon={GitCompareArrows}>Compare</Button>
          <Button as={Link} to={`/analyze/${r.document_id}`} size="sm" variant="ghost" icon={RefreshCw}>Change perspective</Button>
        </div>
      </div>

      <Scorecard result={r} onSelectFinding={(fid) => select(fid, 'score')} />

      {r.engine.warnings.map((w) => (
        <Callout key={w} tone="info" className="mt-4">{w}</Callout>
      ))}

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_440px]">
        <div className="flex h-[calc(100vh-7rem)] min-h-[560px] flex-col lg:sticky lg:top-20">
          <div className="mb-3 flex items-center gap-3">
            <h2 className="font-serif text-lg font-semibold">Document</h2>
            <span className="text-xs text-muted">{r.clauses.length} clauses · click a highlight to see the finding</span>
            {canPdf && (
              <div className="ml-auto flex items-center gap-1 rounded-lg bg-sunken/70 p-0.5 text-xs">
                {[
                  ['clauses', 'Clause view', ScrollText],
                  ['pdf', 'Original PDF', FileText],
                ].map(([k, label, Icon]) => (
                  <button key={k} onClick={() => setView(k)} className={cx('inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1 font-medium', view === k ? 'bg-surface shadow-card' : 'text-muted')}>
                    <Icon className="size-3.5" /> {label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="min-h-0 flex-1">
            {!d ? (
              doc.isError ? <Callout tone="error">{doc.error.message}</Callout> : <div className="grid h-full place-items-center"><Spinner /></div>
            ) : view === 'pdf' && canPdf ? (
              <Suspense fallback={<div className="grid h-full place-items-center"><Spinner /></div>}>
                <PdfViewer url={api.documentFileUrl(d.id)} findings={r.findings} />
              </Suspense>
            ) : (
              <DocumentViewer ref={viewer} text={d.text} clauses={r.clauses} findings={r.findings} activeId={activeId} onSelect={select} />
            )}
          </div>
        </div>

        <div className="h-[calc(100vh-7rem)] min-h-[560px] lg:sticky lg:top-20">
          <FindingsRail
            findings={r.findings}
            benchmarks={r.benchmarks}
            tab={tab}
            onTab={setTab}
            activeId={activeId}
            onSelect={select}
            onJumpClause={(f) => select(f.id, 'clause')}
            onJumpBenchmark={(b) => {
              setView('clauses')
              if (b.clause_id) setTimeout(() => viewer.current?.scrollToClause(b.clause_id), 60)
            }}
          />
        </div>
      </div>

      <ChatDrawer
        open={chatOpen}
        onOpenChange={setChatOpen}
        result={r}
        onCite={(cid) => {
          setChatOpen(false)
          setView('clauses')
          setTimeout(() => viewer.current?.scrollToClause(cid), 250)
        }}
      />
    </div>
  )
}
