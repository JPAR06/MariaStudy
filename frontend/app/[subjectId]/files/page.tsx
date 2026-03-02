"use client"

import { useState, use, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Upload, Trash2, FileText } from "lucide-react"
import { api, type FileRecord } from "@/lib/api"
import { PageHeader } from "@/components/shared/PageHeader"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

interface UploadState {
  filename: string
  step: string
  pct: number
  done: boolean
  error: string | null
}

export default function FilesPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = use(params)
  const qc = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [uploads, setUploads] = useState<UploadState[]>([])
  const [enableImages, setEnableImages] = useState(false)
  const [fileType, setFileType] = useState<"notes" | "exercises">("notes")

  const { data: subject, refetch } = useQuery({
    queryKey: ["subjects", subjectId],
    queryFn: () => api.subjects.get(subjectId),
  })

  async function handleFiles(files: FileList | null) {
    if (!files) return
    for (const file of Array.from(files)) {
      const uploadState: UploadState = {
        filename: file.name, step: "A enviar…", pct: 0, done: false, error: null,
      }
      setUploads((prev) => [...prev, uploadState])

      const formData = new FormData()
      formData.append("file", file)
      formData.append("enable_images", String(enableImages))
      formData.append("file_type", fileType)

      try {
        const res = await fetch(`/api/subjects/${subjectId}/files`, {
          method: "POST",
          body: formData,
        })
        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ""
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            try {
              const data = JSON.parse(line.slice(6))
              setUploads((prev) =>
                prev.map((u) =>
                  u.filename === file.name
                    ? {
                        ...u,
                        step: data.done ? "Concluído!" : (data.step ?? u.step),
                        pct: data.done ? 100 : (data.pct ?? u.pct),
                        done: data.done ?? false,
                      }
                    : u,
                ),
              )
            } catch {}
          }
        }
        refetch()
        qc.invalidateQueries({ queryKey: ["subjects"] })
      } catch (err) {
        setUploads((prev) =>
          prev.map((u) =>
            u.filename === file.name ? { ...u, error: String(err), done: true } : u,
          ),
        )
      }
    }
  }

  async function handleDelete(filename: string) {
    await api.files.delete(subjectId, filename)
    refetch()
    qc.invalidateQueries({ queryKey: ["subjects"] })
  }

  async function handleToggleType(filename: string, current: string) {
    const newType = current === "notes" ? "exercises" : "notes"
    await api.files.setType(subjectId, filename, newType)
    refetch()
  }

  if (!subject) return null

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <PageHeader title="Ficheiros" subtitle={subject.name} />

      {/* Upload area */}
      <div
        className="border-2 border-dashed border-border rounded-card p-10 text-center mb-6 cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-all"
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handleFiles(e.dataTransfer.files) }}
      >
        <Upload className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
        <p className="text-sm font-medium text-foreground mb-1">
          Arrasta ficheiros ou clica para selecionar
        </p>
        <p className="text-xs text-muted-foreground">PDF, TXT ou MD</p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* Options */}
      <div className="flex gap-4 mb-6 flex-wrap">
        <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={enableImages}
            onChange={(e) => setEnableImages(e.target.checked)}
            className="rounded"
          />
          Extrair legendas de imagens (mais lento)
        </label>
        <div className="flex gap-2">
          {(["notes", "exercises"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setFileType(t)}
              className={cn(
                "px-3 py-1 rounded-full text-xs font-medium transition-all border",
                fileType === t
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
            >
              {t === "notes" ? "📚 Apontamentos" : "📝 Exercícios"}
            </button>
          ))}
        </div>
      </div>

      {/* Active uploads */}
      {uploads.filter((u) => !u.done || u.error).length > 0 && (
        <div className="space-y-3 mb-6">
          {uploads.filter((u) => !u.done).map((u) => (
            <div key={u.filename} className="p-4 rounded-card bg-card border border-border shadow-card">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-foreground truncate">{u.filename}</p>
                <p className="text-xs text-muted-foreground ml-2 shrink-0">{u.step}</p>
              </div>
              <Progress value={u.pct} className="h-1.5" />
            </div>
          ))}
        </div>
      )}

      {/* File list */}
      <div className="space-y-2">
        {subject.files.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            Sem ficheiros ainda. Faz upload para começar.
          </p>
        ) : (
          subject.files.map((f) => (
            <FileRow
              key={f.name}
              file={f}
              onDelete={() => handleDelete(f.name)}
              onToggleType={() => handleToggleType(f.name, f.type)}
            />
          ))
        )}
      </div>
    </div>
  )
}

function FileRow({ file, onDelete, onToggleType }: {
  file: FileRecord
  onDelete: () => void
  onToggleType: () => void
}) {
  return (
    <div className="flex items-center gap-3 p-4 rounded-card bg-card border border-border shadow-card">
      <FileText className="w-5 h-5 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
        <p className="text-xs text-muted-foreground">{file.pages} páginas</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleType}
          className={cn(
            "px-2.5 py-1 rounded-full text-xs font-medium transition-colors",
            file.type === "exercises"
              ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
              : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
          )}
        >
          {file.type === "exercises" ? "📝 Exercícios" : "📚 Apontamentos"}
        </button>
        <button
          onClick={onDelete}
          className="p-1.5 rounded-[6px] hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
