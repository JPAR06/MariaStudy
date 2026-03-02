"use client"

import { useState, use } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, X } from "lucide-react"
import { api } from "@/lib/api"
import { PageHeader } from "@/components/shared/PageHeader"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import ReactMarkdown from "react-markdown"

export default function TopicsPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = use(params)
  const qc = useQueryClient()
  const [newTopic, setNewTopic] = useState("")
  const [adding, setAdding] = useState(false)

  const { data: subject, refetch } = useQuery({
    queryKey: ["subjects", subjectId],
    queryFn: () => api.subjects.get(subjectId),
  })

  const topics = subject?.topics ?? []

  async function handleDelete(topic: string) {
    await api.subjects.deleteTopic(subjectId, topic)
    refetch()
    qc.invalidateQueries({ queryKey: ["subjects", subjectId] })
  }

  async function handleAdd() {
    const t = newTopic.trim()
    if (!t || topics.includes(t)) return
    setAdding(true)
    try {
      const updated = [...topics, t]
      await fetch(`/api/subjects/${subjectId}/topics`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated),
      })
      setNewTopic("")
      refetch()
    } finally {
      setAdding(false)
    }
  }

  if (!subject) return null

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <PageHeader title="Tópicos" subtitle={subject.name} />

      {/* Topic chips */}
      <div className="flex flex-wrap gap-2 mb-6">
        {topics.map((t) => (
          <div key={t} className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-medium">
            {t}
            <button onClick={() => handleDelete(t)} className="ml-1 hover:text-primary/60 transition-colors">
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
        {topics.length === 0 && (
          <p className="text-sm text-muted-foreground">Sem tópicos ainda. Adiciona abaixo ou carrega um ficheiro para gerar automaticamente.</p>
        )}
      </div>

      {/* Add topic */}
      <div className="flex gap-2 mb-10">
        <Input
          placeholder="Novo tópico…"
          value={newTopic}
          onChange={(e) => setNewTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          className="max-w-xs"
        />
        <Button variant="outline" onClick={handleAdd} disabled={adding || !newTopic.trim()} className="gap-1.5">
          <Plus className="w-4 h-4" /> Adicionar
        </Button>
      </div>

      {/* Summary */}
      {subject.summary && (
        <div>
          <h2 className="text-base font-semibold text-foreground mb-3">Resumo</h2>
          <div className="p-5 rounded-card bg-card border border-border shadow-card prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{subject.summary}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}
