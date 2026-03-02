"use client"

import { X } from "lucide-react"
import { api } from "@/lib/api"

interface PDFViewerProps {
  subjectId: string
  filename: string
  page?: number
  onClose: () => void
}

export function PDFViewer({ subjectId, filename, page, onClose }: PDFViewerProps) {
  const url = api.files.viewerUrl(subjectId, filename, page)

  return (
    <div className="flex flex-col h-full border-l border-border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{filename}</p>
          {page && <p className="text-xs text-muted-foreground">Página {page}</p>}
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-[6px] hover:bg-muted transition-colors ml-3 shrink-0"
        >
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
      {/* PDF iframe */}
      <iframe
        src={url}
        className="flex-1 w-full"
        title={`${filename} página ${page}`}
      />
    </div>
  )
}
