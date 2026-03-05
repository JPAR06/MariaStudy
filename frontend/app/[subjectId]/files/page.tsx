"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, FileText, Trash2, Upload, Eye } from "lucide-react"
import { api, type FileRecord } from "@/lib/api"
import { useUpload } from "@/lib/upload-context"
import { cn } from "@/lib/utils"

export default function FilesPage() {
  const params = useParams()
  const subjectId = params.subjectId as string
  const qc = useQueryClient()

  const { data: subject } = useQuery({
    queryKey: ["subjects", subjectId],
    queryFn: () => api.subjects.get(subjectId),
    staleTime: 30_000,
  })

  const files: FileRecord[] = useMemo(() => subject?.files ?? [], [subject])

  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const { uploads: allUploads, startUpload } = useUpload()
  const uploads = allUploads.filter((u) => u.subjectId === subjectId)
  const [uploadFileType, setUploadFileType] = useState<"notes" | "exercises">("notes")
  const [uploadEnableImages, setUploadEnableImages] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Auto-select first file
  useEffect(() => {
    if (!selectedFile && files.length > 0) {
      setSelectedFile(files[0].name)
    }
  }, [files, selectedFile])

  // Fetch PDF as blob — Chrome renders blob URLs inline regardless of "Download PDFs" setting
  useEffect(() => {
    if (!selectedFile) { setPdfBlobUrl(null); return }
    let cancelled = false
    const url = api.files.viewerUrl(subjectId, selectedFile)
    setPdfLoading(true)
    setPdfBlobUrl(null)
    fetch(url)
      .then((r) => r.blob())
      .then((blob) => {
        if (cancelled) return
        setPdfBlobUrl(URL.createObjectURL(blob))
      })
      .catch(() => { if (!cancelled) setPdfBlobUrl(null) })
      .finally(() => { if (!cancelled) setPdfLoading(false) })
    return () => {
      cancelled = true
      setPdfBlobUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return null })
    }
  }, [subjectId, selectedFile])

  async function handleDeleteFile(filename: string) {
    await api.files.delete(subjectId, filename)
    if (selectedFile === filename) setSelectedFile(null)
    await qc.invalidateQueries({ queryKey: ["subjects", subjectId] })
  }

  function handleUploadFiles(fileList: FileList | null) {
    if (!fileList) return
    for (const file of Array.from(fileList)) {
      startUpload(subjectId, file, uploadFileType, uploadEnableImages, async () => {
        await qc.invalidateQueries({ queryKey: ["subjects", subjectId] })
        setSelectedFile(file.name)
      })
    }
  }

  return (
    <div className="flex h-screen flex-col bg-[var(--bg)] text-[var(--fg)]">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-zinc-800/60 px-6 py-4">
        <Link
          href={`/${subjectId}`}
          className="flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-200"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Voltar
        </Link>
        <span className="text-zinc-700">/</span>
        <span className="text-sm font-medium text-zinc-300">{subject?.name ?? "…"}</span>
        <span className="text-zinc-700">/</span>
        <span className="text-sm text-zinc-500">Ficheiros</span>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Left panel — file list + upload */}
        <div className="flex w-80 shrink-0 flex-col gap-4 border-r border-zinc-800/60 overflow-y-auto p-5">
          {/* Upload area */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border border-dashed border-zinc-700 px-4 py-6 text-center transition-colors hover:border-blue-500/50 hover:bg-blue-500/5"
          >
            <Upload className="h-5 w-5 text-zinc-500" />
            <p className="text-xs text-zinc-400">Clica para fazer upload de PDF</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={(e) => handleUploadFiles(e.target.files)}
            />
          </div>

          {/* Upload options */}
          <div className="flex items-center gap-3">
            <select
              value={uploadFileType}
              onChange={(e) => setUploadFileType(e.target.value as "notes" | "exercises")}
              className="flex-1 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-300 focus:outline-none"
            >
              <option value="notes">Notas</option>
              <option value="exercises">Exercícios</option>
            </select>
            <label className="flex items-center gap-1.5 text-xs text-zinc-400 cursor-pointer">
              <input
                type="checkbox"
                checked={uploadEnableImages}
                onChange={(e) => setUploadEnableImages(e.target.checked)}
                className="rounded"
              />
              Imagens
            </label>
          </div>

          {/* Upload progress */}
          {uploads.length > 0 && (
            <div className="flex flex-col gap-2">
              {uploads.map((u) => (
                <div key={u.id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-3">
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="truncate text-xs text-zinc-300">{u.filename}</span>
                    {u.done && !u.error && <span className="shrink-0 text-[10px] text-emerald-400">✓</span>}
                    {u.error && <span className="shrink-0 text-[10px] text-red-400">✗</span>}
                  </div>
                  {!u.done && (
                    <>
                      <div className="h-1 w-full overflow-hidden rounded-full bg-zinc-800">
                        <div
                          className="h-full rounded-full bg-blue-500 transition-all duration-300"
                          style={{ width: `${u.pct}%` }}
                        />
                      </div>
                      <p className="mt-1 text-[10px] text-zinc-500">{u.step}</p>
                    </>
                  )}
                  {u.error && <p className="text-[10px] text-red-400">{u.error}</p>}
                </div>
              ))}
            </div>
          )}

          {/* File list */}
          <div className="flex flex-col gap-1.5">
            {files.length === 0 && (
              <p className="py-4 text-center text-xs text-zinc-500">Sem ficheiros. Faz upload acima.</p>
            )}
            {files.map((file) => (
              <div
                key={file.name}
                className={cn(
                  "group flex items-center gap-2 rounded-xl border p-2.5 transition-colors",
                  selectedFile === file.name
                    ? "border-blue-500/40 bg-blue-500/10"
                    : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700",
                )}
              >
                <FileText className="h-4 w-4 shrink-0 text-zinc-500" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs text-zinc-300">{file.name}</p>
                  <div className="mt-0.5 flex items-center gap-1.5">
                    <span className="rounded-full bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500">
                      {file.pages}p
                    </span>
                    <span
                      className={cn(
                        "rounded-full px-1.5 py-0.5 text-[10px]",
                        file.type === "exercises"
                          ? "bg-amber-500/15 text-amber-300"
                          : "bg-blue-500/15 text-blue-300",
                      )}
                    >
                      {file.type === "exercises" ? "Exercícios" : "Notas"}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => { setSelectedFile(file.name) }}
                  className="shrink-0 rounded-md p-1 text-zinc-600 opacity-0 transition-all hover:bg-blue-400/10 hover:text-blue-400 group-hover:opacity-100"
                  title="Pré-visualizar"
                >
                  <Eye className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => handleDeleteFile(file.name)}
                  className="shrink-0 rounded-md p-1 text-zinc-600 opacity-0 transition-all hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100"
                  title="Eliminar"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Right panel — PDF preview */}
        <div className="flex flex-1 flex-col p-5">
          {selectedFile ? (
            <div className="relative flex h-full flex-col overflow-hidden rounded-2xl border border-zinc-800">
              {pdfLoading && (
                <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
                  A carregar PDF…
                </div>
              )}
              {!pdfLoading && pdfBlobUrl && (
                <>
                  <iframe
                    key={pdfBlobUrl}
                    title="PDF preview"
                    src={pdfBlobUrl}
                    className="h-full w-full flex-1 bg-zinc-950"
                  />
                  <a
                    href={api.files.viewerUrl(subjectId, selectedFile)}
                    target="_blank"
                    rel="noreferrer"
                    className="absolute bottom-3 right-3 rounded-full border border-zinc-600 bg-zinc-900/80 px-3 py-1 text-[11px] text-zinc-400 backdrop-blur-sm hover:border-zinc-400 hover:text-zinc-200"
                  >
                    Abrir em nova aba ↗
                  </a>
                </>
              )}
              {!pdfLoading && !pdfBlobUrl && (
                <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
                  Não foi possível carregar o PDF.
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-zinc-800 text-center">
              <FileText className="h-10 w-10 text-zinc-700" />
              <p className="text-sm text-zinc-500">Seleciona um ficheiro para pré-visualizar.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
