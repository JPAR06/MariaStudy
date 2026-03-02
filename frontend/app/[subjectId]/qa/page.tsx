"use client"

import { useState, use, useRef, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Send } from "lucide-react"
import { api, type Source } from "@/lib/api"
import { ChatMessage } from "@/components/qa/ChatMessage"
import { PDFViewer } from "@/components/qa/PDFViewer"
import { TopicChip } from "@/components/shared/TopicChip"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { PageHeader } from "@/components/shared/PageHeader"
import { cn } from "@/lib/utils"

interface Message {
  role: "user" | "assistant"
  content: string
  sources?: Source[]
}

export default function QAPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = use(params)

  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState("")
  const [topicFilter, setTopicFilter] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [pdfSource, setPdfSource] = useState<Source | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: subject } = useQuery({
    queryKey: ["subjects", subjectId],
    queryFn: () => api.subjects.get(subjectId),
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function handleSubmit() {
    if (!question.trim() || loading) return
    const q = question.trim()
    setQuestion("")
    setMessages((prev) => [...prev, { role: "user", content: q }])
    setLoading(true)
    try {
      const res = await api.qa.ask(subjectId, q, topicFilter ?? undefined)
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer, sources: res.sources }])
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Ocorreu um erro. Tenta de novo." }])
    } finally {
      setLoading(false)
    }
  }

  const topics = subject?.topics ?? []

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Main chat area */}
      <div className={cn("flex flex-col flex-1 min-w-0", pdfSource && "border-r border-border")}>
        <div className="px-6 py-4 border-b border-border shrink-0">
          <PageHeader title="Q&A" subtitle={subject?.name} className="mb-0" />
          {/* Topic filter */}
          {topics.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              <button
                onClick={() => setTopicFilter(null)}
                className={cn(
                  "px-3 py-1 rounded-full text-xs font-medium transition-all border",
                  topicFilter === null
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border text-muted-foreground hover:bg-muted",
                )}
              >
                Tudo
              </button>
              {topics.map((t) => (
                <TopicChip
                  key={t}
                  label={t}
                  active={topicFilter === t}
                  onClick={() => setTopicFilter(topicFilter === t ? null : t)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-4xl mb-4">💬</div>
              <p className="text-foreground font-medium">Faz uma pergunta sobre {subject?.name}</p>
              <p className="text-sm text-muted-foreground mt-1">
                As respostas são baseadas nos teus apontamentos com citações.
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessage
              key={i}
              role={msg.role}
              content={msg.content}
              sources={msg.sources}
              onCitationClick={(src) => setPdfSource(src)}
            />
          ))}
          {loading && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-full bg-muted flex items-center justify-center text-xs font-semibold text-muted-foreground shrink-0">AI</div>
              <div className="px-4 py-3 rounded-[14px] rounded-tl-sm bg-card border border-border">
                <span className="inline-flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "300ms" }} />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-border shrink-0">
          <div className="flex gap-2 items-end">
            <Textarea
              placeholder="Pergunta sobre os teus apontamentos…"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit()
                }
              }}
              rows={1}
              className="resize-none min-h-10 max-h-32"
            />
            <Button
              size="icon"
              onClick={handleSubmit}
              disabled={loading || !question.trim()}
              className="shrink-0"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-1.5">Enter para enviar · Shift+Enter para nova linha</p>
        </div>
      </div>

      {/* PDF Side panel */}
      {pdfSource && (
        <div className="w-[480px] shrink-0 h-screen">
          <PDFViewer
            subjectId={subjectId}
            filename={pdfSource.file}
            page={pdfSource.page}
            onClose={() => setPdfSource(null)}
          />
        </div>
      )}
    </div>
  )
}
