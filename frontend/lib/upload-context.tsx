"use client"

import { createContext, useCallback, useContext, useState } from "react"
import { getToken } from "@/lib/auth"

export interface UploadItem {
  id: string
  subjectId: string
  filename: string
  step: string
  pct: number
  done: boolean
  error: string | null
}

interface UploadContextType {
  uploads: UploadItem[]
  activeUploads: UploadItem[]
  startUpload: (
    subjectId: string,
    file: File,
    fileType: string,
    enableImages: boolean,
    onComplete?: () => void,
  ) => void
}

const UploadContext = createContext<UploadContextType | null>(null)

export function UploadProvider({ children }: { children: React.ReactNode }) {
  const [uploads, setUploads] = useState<UploadItem[]>([])

  const update = useCallback((id: string, patch: Partial<UploadItem>) => {
    setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, ...patch } : u)))
  }, [])

  const startUpload = useCallback(
    async (
      subjectId: string,
      file: File,
      fileType: string,
      enableImages: boolean,
      onComplete?: () => void,
    ) => {
      const id = `${subjectId}:${file.name}:${Date.now()}`
      setUploads((prev) => [
        ...prev,
        { id, subjectId, filename: file.name, step: "A preparar...", pct: 0, done: false, error: null },
      ])

      const formData = new FormData()
      formData.append("file", file)
      formData.append("enable_images", String(enableImages))
      formData.append("file_type", fileType)

      try {
        const token = getToken()
        const res = await fetch(`/api/subjects/${subjectId}/files`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        })

        if (!res.ok) {
          const details = await res.text().catch(() => "")
          throw new Error(`Upload falhou (${res.status})${details ? `: ${details}` : ""}`)
        }
        if (!res.body) {
          throw new Error("Upload falhou: resposta sem stream de progresso")
        }

        const reader = res.body.getReader()
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
              if (data.error) {
                update(id, { error: String(data.error), done: true })
                continue
              }
              update(id, {
                step: data.done ? "Concluido" : (data.step ?? ""),
                pct: data.pct ?? 0,
                done: data.done ?? false,
                error: data.error ?? null,
              })
            } catch {
              // ignore malformed event chunks
            }
          }
        }

        setUploads((prev) =>
          prev.map((u) =>
            u.id === id
              ? (u.error ? u : { ...u, done: true, pct: 100, step: "Concluido" })
              : u,
          ),
        )
        onComplete?.()
      } catch (err) {
        update(id, { error: String(err), done: true })
      }
    },
    [update],
  )

  const activeUploads = uploads.filter((u) => !u.done)

  return (
    <UploadContext.Provider value={{ uploads, activeUploads, startUpload }}>
      {children}
    </UploadContext.Provider>
  )
}

export function useUpload() {
  const ctx = useContext(UploadContext)
  if (!ctx) throw new Error("useUpload must be used within UploadProvider")
  return ctx
}
