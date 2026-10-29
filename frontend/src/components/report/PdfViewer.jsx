import { useCallback, useMemo, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/TextLayer.css'
import { normalizeForMatch } from '../../lib/highlights'
import { Callout, Spinner } from '../ui'

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()

const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

export default function PdfViewer({ url, findings }) {
  const [pages, setPages] = useState(0)
  const [width, setWidth] = useState(720)

  const quotes = useMemo(
    () =>
      findings
        .filter((f) => f.quote && !f.favorable && f.kind !== 'missing')
        .map((f) => ({ q: normalizeForMatch(f.quote), cls: f.severity === 'critical' ? 'pdf-hl pdf-hl-critical' : f.severity === 'medium' ? 'pdf-hl pdf-hl-medium' : 'pdf-hl' })),
    [findings],
  )

  const renderText = useCallback(
    ({ str }) => {
      const n = normalizeForMatch(str)
      if (n.length >= 10) {
        const hit = quotes.find(({ q }) => q.includes(n))
        if (hit) return `<mark class="${hit.cls}">${escapeHtml(str)}</mark>`
      }
      return escapeHtml(str)
    },
    [quotes],
  )

  const measureRef = useCallback((node) => {
    if (!node) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.min(900, entry.contentRect.width - 32)))
    ro.observe(node)
  }, [])

  return (
    <div ref={measureRef} className="scrollbar-thin h-full overflow-y-auto rounded-2xl border border-line bg-sunken/60 p-4">
      <Document
        file={url}
        onLoadSuccess={({ numPages }) => setPages(numPages)}
        loading={<div className="grid h-64 place-items-center"><Spinner /></div>}
        error={<Callout tone="error">Could not render the original PDF. The clause view still shows every finding.</Callout>}
      >
        {Array.from({ length: pages }, (_, i) => (
          <div key={i} className="mx-auto mb-4 w-fit overflow-hidden rounded-md shadow-card">
            <Page pageNumber={i + 1} width={width} renderAnnotationLayer={false} customTextRenderer={renderText} />
          </div>
        ))}
      </Document>
    </div>
  )
}
