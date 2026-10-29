import { useMutation } from '@tanstack/react-query'
import { ArrowUp, MessageSquareText } from 'lucide-react'
import { Fragment, useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { Callout, cx, Drawer, Spinner } from '../ui'

const SUGGESTIONS = {
  offer_letter: ['What happens if I resign in the first year?', 'Can they change my salary or role?', 'Is there a non-compete?'],
  employment_agreement: ['What is my notice period?', 'Who owns what I build?', 'Can they terminate without cause?'],
  msa_saas: ['How can we exit this contract?', 'Can the vendor use our data?', 'What is the liability cap?'],
  tos: ['Can they change these terms?', 'How do disputes get resolved?', 'Can they delete my account?'],
  privacy_policy: ['Do they sell my data?', 'How long is my data kept?', 'How do I delete my data?'],
  dpa_compliance: ['How fast must breaches be reported?', 'Can they use sub-processors?', 'What happens to data at the end?'],
}

function Answer({ text, onCite }) {
  const parts = text.split(/(\[C\d+\])/g)
  return (
    <div className="whitespace-pre-wrap text-[14px] leading-relaxed">
      {parts.map((p, i) => {
        const m = p.match(/^\[(C\d+)\]$/)
        return m ? (
          <button key={i} onClick={() => onCite(m[1])} className="mx-0.5 cursor-pointer rounded bg-accent-soft px-1 font-mono text-[11px] font-semibold text-accent hover:brightness-95">
            {m[1]}
          </button>
        ) : (
          <Fragment key={i}>{p}</Fragment>
        )
      })}
    </div>
  )
}

export default function ChatDrawer({ open, onOpenChange, result, onCite }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const endRef = useRef(null)
  const ask = useMutation({
    mutationFn: (question) => api.chat(result.analysis_id, question, messages.map(({ role, content }) => ({ role, content }))),
    onSuccess: (res) => setMessages((m) => [...m, { role: 'assistant', content: res.answer, citations: res.citations, mode: res.mode }]),
  })

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, ask.isPending])

  const send = (q) => {
    const question = (q ?? input).trim()
    if (!question || ask.isPending) return
    setMessages((m) => [...m, { role: 'user', content: question }])
    setInput('')
    ask.mutate(question)
  }

  const suggestions = SUGGESTIONS[result.doc_type] || ['What are my main obligations?', 'How can this agreement be terminated?', 'Who is liable if something goes wrong?']

  return (
    <Drawer open={open} onOpenChange={onOpenChange} title="Ask the document" description="Answers come only from this document and cite the clauses they rely on.">
      <div className="flex h-full flex-col">
        <div className="flex-1 space-y-4 p-6">
          {messages.length === 0 && (
            <div className="rounded-xl border border-dashed border-line-strong p-5">
              <MessageSquareText className="size-5 text-muted" />
              <p className="mt-2 text-sm text-muted">Try one of these:</p>
              <div className="mt-3 flex flex-col gap-2">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)} className="cursor-pointer rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm hover:border-ink">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={cx('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div className={cx('max-w-[88%] rounded-2xl px-4 py-3', m.role === 'user' ? 'bg-ink text-paper' : 'border border-line bg-surface-2')}>
                {m.role === 'user' ? <div className="text-[14px]">{m.content}</div> : <Answer text={m.content} onCite={onCite} />}
                {m.citations?.length > 0 && (
                  <div className="mt-3 space-y-1.5 border-t border-line pt-2">
                    {m.citations.map((c) => (
                      <button key={c.clause_id} onClick={() => onCite(c.clause_id)} className="block w-full cursor-pointer rounded-md px-2 py-1 text-left text-xs hover:bg-sunken/60">
                        <span className="font-mono font-semibold text-accent">{c.clause_id}</span> <span className="font-medium">{c.label}</span>
                        <span className="mt-0.5 block line-clamp-2 font-serif text-muted">{c.excerpt}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {ask.isPending && (
            <div className="flex items-center gap-2 text-sm text-muted">
              <Spinner className="size-4" /> Reading the relevant clauses...
            </div>
          )}
          {ask.isError && <Callout tone="error">{ask.error.message}</Callout>}
          <div ref={endRef} />
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            send()
          }}
          className="sticky bottom-0 border-t border-line bg-surface p-4"
        >
          <div className="flex items-end gap-2 rounded-xl border border-line bg-surface-2 p-2 focus-within:border-accent">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
              rows={1}
              placeholder="Ask about this document..."
              className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
              data-testid="chat-input"
            />
            <button type="submit" disabled={!input.trim() || ask.isPending} className="grid size-8 cursor-pointer place-items-center rounded-lg bg-ink text-paper disabled:opacity-40" aria-label="Send">
              <ArrowUp className="size-4" />
            </button>
          </div>
          <p className="mt-2 text-[11px] text-muted">Not legal advice. Answers are limited to what this document says.</p>
        </form>
      </div>
    </Drawer>
  )
}
