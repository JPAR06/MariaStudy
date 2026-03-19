"use client"

import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  BarChart3,
  BookOpen,
  Download,
  FileText,
  Layers3,
  MessageSquare,
  Plus,
  Sparkles,
  Upload,
  X,
} from "lucide-react"
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis } from "recharts"
import { api, type FlashcardInDB, type QuizQuestion, type Source } from "@/lib/api"
import { getToken } from "@/lib/auth"
import { useUpload } from "@/lib/upload-context"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { TopicChip } from "@/components/shared/TopicChip"
import { cn, clozeHighlight, clozeToBlank } from "@/lib/utils"
import PdfPageViewer from "@/components/PdfPageViewer"


type StudioView =
  | "dashboard"
  | "flashcards"
  | "quiz"
  | "qa"
  | "summary"
  | "notes"
  | "preview"

// Add new entries here — UI adapts automatically
const UPLOAD_FILE_TYPES = [
  { value: "notes",     label: "📚 Apontamentos" },
  { value: "exercises", label: "📝 Exercícios" },
]

type UploadPhase = { label: string; barClass: string; dotClass: string }

type PreviewReference = {
  file: string
  page?: number
  query?: string
}

function getUploadPhase(step: string, pct: number): UploadPhase {
  if (/finalizar/i.test(step))       return { label: "A finalizar…",           barClass: "bg-amber-500",  dotClass: "bg-amber-400" }
  if (/indexar|vetores/i.test(step)) return { label: "A indexar…",             barClass: "bg-violet-500", dotClass: "bg-violet-400" }
  if (/embeddings/i.test(step))      return { label: "A calcular embeddings…", barClass: "bg-blue-500",   dotClass: "bg-blue-400" }
  if (pct > 0)                       return { label: "A extrair texto…",        barClass: "bg-sky-500",    dotClass: "bg-sky-400" }
  return { label: "A preparar…", barClass: "bg-zinc-600", dotClass: "bg-zinc-500" }
}

function parseUploadChunks(step: string): { done: number; total: number } | null {
  const m = step.match(/(\d+)\/(\d+)\s+chunks/i)
  return m ? { done: parseInt(m[1]), total: parseInt(m[2]) } : null
}

export default function SubjectDashboardPage({ params }: { params: { subjectId: string } }) {
  const { subjectId } = params
  const qc = useQueryClient()

  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [topic, setTopic] = useState("Toda a UC")
  const [flashcardTopics, setFlashcardTopics] = useState<string[]>([])
  const [quizTopics, setQuizTopics] = useState<string[]>([])
  const [summaryTopic, setSummaryTopic] = useState<string | null>(null)
  const [previewReference, setPreviewReference] = useState<PreviewReference | null>(null)
  const [nCards, setNCards] = useState(10)
  const [quickNotes, setQuickNotes] = useState("")
  const [studioView, setStudioView] = useState<StudioView>("dashboard")
  const [updatingStatus, setUpdatingStatus] = useState(false)
  const [generatingCards, setGeneratingCards] = useState(false)
  const [flashcardMsg, setFlashcardMsg] = useState<string | null>(null)
  const [studyDeck, setStudyDeck] = useState<FlashcardInDB[]>([])
  const [cardIdx, setCardIdx] = useState(0)
  const [showBack, setShowBack] = useState(false)
  const [savingResult, setSavingResult] = useState(false)
  const [sessionDone, setSessionDone] = useState(0) // card count of last completed session
  const [quizN, setQuizN] = useState(10)
  const [quizDifficulty, setQuizDifficulty] = useState("Médio")
  const [generatingQuiz, setGeneratingQuiz] = useState(false)
  const [quizMsg, setQuizMsg] = useState<string | null>(null)
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([])
  const [quizPhase, setQuizPhase] = useState<"config" | "taking" | "results">("config")
  const [quizFinalAnswers, setQuizFinalAnswers] = useState<Array<{ selected: string; isCorrect: boolean }>>([])
  const [qaQuestion, setQaQuestion] = useState("")
  const [askingQa, setAskingQa] = useState(false)
  const [qaAnswer, setQaAnswer] = useState("")
  const [qaSources, setQaSources] = useState<Source[]>([])
  const [qaMsg, setQaMsg] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadFileType, setUploadFileType] = useState<string>("notes")
  const [uploadEnableImages, setUploadEnableImages] = useState(false)
  const { uploads: allUploads, startUpload } = useUpload()
  const uploads = allUploads.filter((u) => u.subjectId === subjectId)

  const { data: subject } = useQuery({
    queryKey: ["subjects", subjectId],
    queryFn: () => api.subjects.get(subjectId),
  })

  const { data: progress, refetch: refetchProgress } = useQuery({
    queryKey: ["progress", subjectId],
    queryFn: () => api.progress.get(subjectId),
  })
  const { data: deck = [], refetch: refetchDeck } = useQuery({
    queryKey: ["flashcards", subjectId],
    queryFn: () => api.flashcards.getDeck(subjectId),
  })
  const { data: savedQuizQuestions = [], refetch: refetchSavedQuiz } = useQuery({
    queryKey: ["quiz-saved", subjectId],
    queryFn: () => api.quiz.getSaved(subjectId),
  })

  const topics = subject?.topics ?? []
  const sortedTopics = [...topics].sort((a, b) => a.localeCompare(b, "pt"))
  const files = subject?.files ?? []
  const previewableFiles = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"))

  useEffect(() => {
    if (!selectedFile && previewableFiles.length > 0) {
      setSelectedFile(previewableFiles[0].name)
    }
  }, [previewableFiles, selectedFile])

  useEffect(() => {
    if (studioView !== "summary") return
    if (topic && topic !== "Toda a UC") setSummaryTopic(topic)
  }, [studioView, topic])

  const [viewerPage, setViewerPage] = useState<number | undefined>(undefined)
  const viewerUrl = selectedFile ? api.files.viewerUrl(subjectId, selectedFile, viewerPage) : null
  const viewerFetchUrl = selectedFile ? api.files.viewerUrl(subjectId, selectedFile) : null

  // Fetch PDF as blob so Chrome renders it inline regardless of "Download PDFs" setting
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfLoadError, setPdfLoadError] = useState(false)
  const pdfFrameUrl = pdfBlobUrl
    ? (viewerPage ? `${pdfBlobUrl}#page=${viewerPage}` : pdfBlobUrl)
    : null
  useEffect(() => {
    if (!viewerFetchUrl) { setPdfBlobUrl(null); setPdfLoadError(false); return }
    let cancelled = false
    setPdfLoading(true)
    setPdfLoadError(false)
    setPdfBlobUrl(null)
    fetch(viewerFetchUrl)
      .then((r) => { if (!r.ok) throw new Error("not ok"); return r.blob() })
      .then((blob) => {
        if (cancelled) return
        const url = URL.createObjectURL(blob)
        setPdfBlobUrl(url)
      })
      .catch(() => { if (!cancelled) { setPdfBlobUrl(null); setPdfLoadError(true) } })
      .finally(() => { if (!cancelled) setPdfLoading(false) })
    return () => {
      cancelled = true
      setPdfBlobUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return null })
    }
  }, [viewerFetchUrl])

  if (!subject) return null

  const srs = progress?.srs_stats
  const quizHistory = progress?.quiz_history ?? []
  const topicStats = progress?.topic_stats ?? []

  const quizAttempts = quizHistory.length
  const quizQuestionsAnswered = quizHistory.reduce((acc, q) => acc + (q.total ?? 0), 0)
  const quizCorrectAnswered = quizHistory.reduce((acc, q) => acc + (q.score ?? 0), 0)
  const quizAccuracyPct = quizQuestionsAnswered ? Math.round((quizCorrectAnswered / quizQuestionsAnswered) * 100) : 0
  const quizTopicBreakdown = Object.entries(
    quizHistory.reduce((acc, q) => {
      const key = q.topic || "Sem tópico"
      if (!acc[key]) acc[key] = { topic: key, total: 0, correct: 0 }
      acc[key].total += q.total ?? 0
      acc[key].correct += q.score ?? 0
      return acc
    }, {} as Record<string, { topic: string; total: number; correct: number }>),
  )
    .map(([, value]) => value)
    .sort((a, b) => b.total - a.total)
    .slice(0, 10)

  const flashcardsAnswered = deck.reduce((sum, card) => sum + (card.reps ?? 0), 0)
  const savedFlashcards = deck.filter((card) => card.favorite).length
  const reviewedCards = deck.filter((card) => (card.reps ?? 0) > 0)
  const reviewedCount = reviewedCards.length
  const difficultCards = reviewedCards.filter((card) => (card.ease ?? 2.5) < 2.3).length
  const mediumCards = reviewedCards.filter((card) => (card.ease ?? 2.5) >= 2.3 && (card.ease ?? 2.5) < 2.7).length
  const easyCards = reviewedCards.filter((card) => (card.ease ?? 2.5) >= 2.7).length
  const avgEase = reviewedCount
    ? Number((reviewedCards.reduce((acc, card) => acc + (card.ease ?? 2.5), 0) / reviewedCount).toFixed(2))
    : 0
  const completionPct = (srs?.total ?? 0) > 0 ? Math.round((reviewedCount / (srs?.total ?? 1)) * 100) : 0
  const studiedTopics = Array.from(new Set(topicStats.map((t) => t.topic).filter(Boolean)))
  const dailyActivity = buildDailyActivity(quizHistory, deck)
  const doneToday = dailyActivity[dailyActivity.length - 1]?.total ?? 0

  const hideSourcesPanel = studioView === "flashcards" || studioView === "quiz"

  async function handleDeleteFile(filename: string) {
    await api.files.delete(subjectId, filename)
    if (selectedFile === filename) setSelectedFile(null)
    await qc.invalidateQueries({ queryKey: ["subjects", subjectId] })
  }

  function openPreviewAtReference(file: string, page?: number, query?: string) {
    setSelectedFile(file)
    setViewerPage(page)
    setPreviewReference({ file, page, query })
    setStudioView("preview")
  }

  function handleUploadFiles(fileList: FileList | null) {
    if (!fileList) return
    for (const file of Array.from(fileList)) {
      startUpload(subjectId, file, uploadFileType, uploadEnableImages, () => {
        qc.invalidateQueries({ queryKey: ["subjects", subjectId] })
      })
    }
  }

  async function handleToggleSubjectStatus() {
    setUpdatingStatus(true)
    try {
      const nextStatus = subject?.status === "finished" ? "active" : "finished"
      await api.subjects.updateStatus(subjectId, nextStatus)
      await qc.invalidateQueries({ queryKey: ["subjects"] })
      await qc.invalidateQueries({ queryKey: ["subjects", subjectId] })
    } finally {
      setUpdatingStatus(false)
    }
  }

  async function handleGenerateFlashcards() {
    if (nCards === 0) {
      setFlashcardMsg("Escolhe um numero de cartas maior que 0.")
      return
    }
    setGeneratingCards(true)
    setFlashcardMsg(null)

    const selectedTopics = flashcardTopics.filter((t) => sortedTopics.includes(t))
    const generationTopic =
      selectedTopics.length > 0
        ? selectedTopics.join(", ")
        : topic === "Toda a UC"
          ? "Toda a UC"
          : topic
    const today = new Date().toISOString().split("T")[0]
    let localDeck: FlashcardInDB[] = []
    let switched = false

    try {
      const token = getToken()
      const res = await fetch(`/api/subjects/${subjectId}/flashcards/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          topic: generationTopic,
          topics: selectedTopics.length > 0 ? selectedTopics : undefined,
          n: nCards,
        }),
      })
      if (!res.ok) throw new Error(`Erro ${res.status}`)

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
            if (data.error) {
              setFlashcardMsg(data.error)
            } else if (data.frente) {
              const card: FlashcardInDB = {
                frente: data.frente,
                verso: data.verso,
                fonte: data.fonte ?? "",
                card_type: data.card_type ?? "basic",
                interval: 1,
                ease: 2.5,
                reps: 0,
                last_reviewed: null,
                next_review: today,
                favorite: false,
                status: "nova",
              }
              localDeck = [...localDeck, card]
              setStudyDeck([...localDeck])
              // Switch to flashcard view on first batch complete (3 cards)
              if (!switched && localDeck.length >= 3) {
                switched = true
                setCardIdx(0)
                setShowBack(false)
                setSessionDone(0)
                setStudioView("flashcards")
              }
            }
          } catch {}
        }
      }
      // If fewer than 3 cards arrived, switch anyway
      if (!switched && localDeck.length > 0) {
        setCardIdx(0)
        setShowBack(false)
        setSessionDone(0)
        setStudioView("flashcards")
      }
      await Promise.all([
        refetchProgress(),
        refetchDeck(),
        qc.invalidateQueries({ queryKey: ["flashcards", subjectId] }),
      ])
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao gerar flashcards."
      setFlashcardMsg(message)
    } finally {
      setGeneratingCards(false)
    }
  }

  async function handleExportAnki() {
    const token = getToken()
    const res = await fetch(`/api/subjects/${subjectId}/flashcards/export/anki`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) return
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${subject?.name ?? "deck"}.apkg`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function handleGenerateQuiz() {
    if (quizN === 0) {
      setQuizMsg("Escolhe um numero de perguntas maior que 0.")
      return
    }
    setGeneratingQuiz(true)
    setQuizMsg(null)
    setQuizQuestions([])
    setQuizFinalAnswers([])

    const selectedTopics = quizTopics.filter((t) => sortedTopics.includes(t))
    const generationTopic =
      selectedTopics.length > 0
        ? selectedTopics.join(", ")
        : topic === "Toda a UC"
          ? "Toda a UC"
          : topic
    // Buffer until MIN_TO_START questions arrive before switching to quiz view
    const MIN_TO_START = Math.min(5, quizN)
    let loadedCount = 0
    let phaseTransitioned = false

    try {
      const token = getToken()
      const res = await fetch(`/api/subjects/${subjectId}/quiz/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          topic: generationTopic,
          topics: selectedTopics.length > 0 ? selectedTopics : undefined,
          n: quizN,
          difficulty: quizDifficulty,
        }),
      })
      if (!res.ok) throw new Error(`Erro ${res.status}`)

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
            if (data.error) {
              setQuizMsg(data.error)
            } else if (data.done) {
              // Stream finished — show quiz if we haven't yet (fewer questions than threshold)
              if (!phaseTransitioned && loadedCount > 0) {
                phaseTransitioned = true
                setQuizPhase("taking")
              }
            } else if (data.pergunta) {
              // New question arrived
              setQuizQuestions((prev) => {
                const next = [...prev, data as QuizQuestion]
                return next
              })
              loadedCount++
              if (!phaseTransitioned && loadedCount >= MIN_TO_START) {
                phaseTransitioned = true
                setQuizPhase("taking")
              }
            }
          } catch {}
        }
      }
      await refetchProgress()
    } catch (err) {
      setQuizMsg(err instanceof Error ? err.message : "Falha ao gerar quiz.")
    } finally {
      setGeneratingQuiz(false)
    }
  }

  async function handleAskQa() {
    setAskingQa(true)
    setQaMsg(null)
    try {
      if (!qaQuestion.trim()) {
        setQaMsg("Escreve uma pergunta.")
        return
      }
      const topicFilter = topic === "Toda a UC" ? undefined : topic
      const res = await api.qa.ask(subjectId, qaQuestion.trim(), topicFilter)
      setQaAnswer(res.answer)
      setQaSources(res.sources)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao obter resposta."
      setQaMsg(message)
    } finally {
      setAskingQa(false)
    }
  }

  function startDueSession() {
    const dueCards = deck.filter((c) => c.status === "para rever" || c.status === "nova")
    if (dueCards.length === 0) {
      setFlashcardMsg("Não há cartas pendentes para rever.")
      return
    }
    setStudyDeck(dueCards)
    setCardIdx(0)
    setShowBack(false)
    setSessionDone(0)
    setFlashcardMsg(null)
    setStudioView("flashcards")
  }

  function startSavedFlashcardsSession() {
    const savedCards = deck.filter((c) => c.favorite)
    if (savedCards.length === 0) {
      setFlashcardMsg("Não há cartões guardados para rever.")
      return
    }
    setStudyDeck(savedCards)
    setCardIdx(0)
    setShowBack(false)
    setSessionDone(0)
    setFlashcardMsg(null)
    setStudioView("flashcards")
  }

  async function handleToggleFlashcardSaved(card: FlashcardInDB) {
    const res = await api.flashcards.toggleFavorite(subjectId, card)
    setStudyDeck((prev) => prev.map((c) => (c.frente === card.frente ? { ...c, favorite: res.favorite } : c)))
    await Promise.all([refetchDeck(), refetchProgress()])
  }

  async function handleToggleSavedQuizQuestion(question: QuizQuestion) {
    await api.quiz.toggleSaved(subjectId, question)
    await refetchSavedQuiz()
  }

  async function handleStudyResult(result: "again" | "hard" | "good" | "easy") {
    if (!studyDeck.length) return
    const current = studyDeck[cardIdx]
    setSavingResult(true)
    try {
      await api.flashcards.saveResult(subjectId, current, result)
      if (cardIdx + 1 < studyDeck.length) {
        setCardIdx((v) => v + 1)
        setShowBack(false)
      } else {
        setSessionDone(studyDeck.length)
        setStudyDeck([])
        setCardIdx(0)
        setShowBack(false)
        setFlashcardMsg(null)
        await Promise.all([refetchProgress(), refetchDeck()])
      }
    } finally {
      setSavingResult(false)
    }
  }

  return (
    <div className="h-full bg-zinc-900 px-6 pb-6 pt-5 text-zinc-100">
      <div className="mb-4 flex items-end justify-between px-1">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-zinc-500">Notebook</p>
          <h1 className="text-4xl font-medium tracking-tight">{subject.name}</h1>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex h-9 items-center rounded-full border px-4 text-sm",
              subject.status === "finished"
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                : "border-blue-500/40 bg-blue-500/10 text-blue-300",
            )}
          >
            {subject.status === "finished" ? "Concluída" : "Ativa"}
          </span>
          <button
            onClick={handleToggleSubjectStatus}
            disabled={updatingStatus}
            className="h-9 rounded-full border border-zinc-700 px-4 text-sm text-zinc-300 transition-colors hover:bg-zinc-800/70 disabled:opacity-60"
          >
            {updatingStatus
              ? "A atualizar..."
              : subject.status === "finished"
                ? "Reabrir UC"
                : "Marcar concluída"}
          </button>
        </div>
      </div>

      <div
        className={cn(
          "grid h-[calc(100%-5.2rem)] grid-cols-1 gap-3",
          hideSourcesPanel
            ? "xl:grid-cols-[330px_minmax(0,1fr)]"
            : "xl:grid-cols-[330px_minmax(0,1fr)_340px]",
        )}
      >
        {!hideSourcesPanel && (
          <aside className="flex min-h-0 flex-col rounded-3xl border border-zinc-700/50 bg-zinc-800/55 xl:order-3">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-zinc-700/50 px-5 py-4">
              <h2 className="text-[2rem] font-normal tracking-tight">Fontes</h2>
            </div>

            {/* Sources content */}
            <div className="flex-1 overflow-auto p-4">
              <div className="space-y-2">
                  {/* Upload toggle button */}
                  <button
                    onClick={() => setUploadOpen((v) => !v)}
                    className="mb-1 flex h-9 w-full items-center justify-center gap-2 rounded-full border border-zinc-700 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700/40"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    {uploadOpen ? "Fechar" : "Adicionar ficheiros"}
                  </button>

                  {/* Inline upload drawer */}
                  {uploadOpen && (
                    <div className="mb-2 rounded-2xl border border-zinc-700/60 bg-zinc-900/60 p-3 space-y-2.5">
                      {/* Type selector */}
                      <select
                        value={uploadFileType}
                        onChange={(e) => setUploadFileType(e.target.value)}
                        className="w-full rounded-xl border border-zinc-700 bg-zinc-800/60 px-3 py-1.5 text-[11px] text-zinc-300 focus:outline-none focus:ring-1 focus:ring-blue-500/50 cursor-pointer"
                      >
                        {UPLOAD_FILE_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                      </select>
                      <label className="flex cursor-pointer items-center gap-2 text-[11px] text-zinc-400">
                        <input
                          type="checkbox"
                          checked={uploadEnableImages}
                          onChange={(e) => setUploadEnableImages(e.target.checked)}
                          className="rounded"
                        />
                        Extrair legendas de imagens (mais lento)
                      </label>
                      {/* Drop zone */}
                      <div
                        className="flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border border-dashed border-zinc-700 py-5 transition-colors hover:border-zinc-500 hover:bg-zinc-800/40"
                        onClick={() => fileInputRef.current?.click()}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={(e) => { e.preventDefault(); handleUploadFiles(e.dataTransfer.files) }}
                      >
                        <Upload className="h-4 w-4 text-zinc-500" />
                        <p className="text-[11px] text-zinc-500">Clica ou arrasta ficheiros</p>
                        <p className="text-[10px] text-zinc-600">PDF, TXT, MD, MP3…</p>
                      </div>
                      <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        accept=".pdf,.txt,.md,.mp3,.m4a,.wav,.webm,.mp4,.ogg,.flac"
                        className="hidden"
                        onChange={(e) => handleUploadFiles(e.target.files)}
                      />
                      {/* Upload progress */}
                      {uploads.filter((u) => !u.done).map((u) => {
                        const phase = getUploadPhase(u.step, u.pct)
                        const chunks = parseUploadChunks(u.step)
                        const indeterminate = isUploadIndeterminate(u)
                        return (
                          <div key={u.filename} className="space-y-1.5 rounded-xl border border-zinc-700/50 bg-zinc-900/40 p-2.5">
                            <div className="flex items-center gap-1.5">
                              <div className={cn("h-1.5 w-1.5 rounded-full shrink-0 animate-pulse", phase.dotClass)} />
                              <p className="flex-1 truncate text-[11px] font-medium text-zinc-300">{u.filename}</p>
                              {!indeterminate && (
                                <span className="shrink-0 text-[10px] font-mono tabular-nums text-zinc-500">{Math.round(u.pct)}%</span>
                              )}
                            </div>
                            <div className="flex items-center justify-between px-0.5">
                              <span className="text-[10px] text-zinc-500">{phase.label}</span>
                              {chunks && <span className="text-[10px] font-mono tabular-nums text-zinc-600">{chunks.done}/{chunks.total} ch</span>}
                            </div>
                            {indeterminate ? (
                              <div className="upload-indeterminate-track h-1 rounded-full" />
                            ) : (
                              <div className="h-1 rounded-full bg-zinc-800 overflow-hidden">
                                <div
                                  className={cn("h-full rounded-full transition-all duration-300", phase.barClass)}
                                  style={{ width: `${u.pct}%` }}
                                />
                              </div>
                            )}
                          </div>
                        )
                      })}
                      {uploads.filter((u) => u.done && !u.error).length > 0 && (
                        <p className="text-[11px] text-emerald-400">
                          ✓ {uploads.filter((u) => u.done && !u.error).length} ficheiro(s) importado(s)
                        </p>
                      )}
                      {uploads.filter((u) => u.error).map((u) => (
                        <p key={u.filename} className="text-[11px] text-red-400">Erro: {u.filename}</p>
                      ))}
                    </div>
                  )}
                  {files.length === 0 && (
                    <p className="px-1 py-2 text-sm text-zinc-500">Sem ficheiros.</p>
                  )}
                  {files.map((file) => {
                    const active = selectedFile === file.name
                    return (
                      <div
                        key={file.name}
                        className={cn(
                          "group rounded-2xl border p-3 transition-colors",
                          active
                            ? "border-zinc-600 bg-zinc-700/40"
                            : "border-zinc-700/60 bg-zinc-900/30 hover:border-zinc-600/60",
                        )}
                      >
                        <div className="flex items-start gap-2">
                          <button
                            onClick={() => { setSelectedFile(file.name); setViewerPage(undefined); setPreviewReference(null); setStudioView("preview") }}
                            className="flex min-w-0 flex-1 items-start gap-2 text-left"
                          >
                            <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-500" />
                            <span className="truncate text-xs leading-relaxed text-zinc-300">{file.name}</span>
                          </button>
                          <button
                            onClick={() => handleDeleteFile(file.name)}
                            className="shrink-0 rounded-md p-1 text-zinc-600 opacity-40 transition-all hover:bg-red-400/10 hover:text-red-400 hover:opacity-100 group-hover:opacity-70"
                            title="Eliminar ficheiro"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <div className="ml-5 mt-1.5 flex items-center gap-2">
                          <span className={cn(
                            "rounded-full px-2 py-0.5 text-[9px] font-medium",
                            file.type === "exercises"
                              ? "bg-violet-500/15 text-violet-400"
                              : "bg-blue-500/15 text-blue-400",
                          )}>
                            {file.type === "exercises" ? "Exercícios" : "Notas"}
                          </span>
                          {file.pages > 0 && (
                            <span className="text-[9px] text-zinc-600">{file.pages}p</span>
                          )}
                        </div>
                        {(file.topics ?? []).length > 0 && (
                          <div className="ml-5 mt-2 flex flex-wrap gap-1">
                            {(file.topics ?? []).map((t) => (
                              <button
                                key={t}
                                onClick={() => setTopic(t)}
                                className={cn(
                                  "rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors",
                                  topic === t
                                    ? "bg-blue-400/20 text-blue-300"
                                    : "text-zinc-500 hover:bg-zinc-700/40 hover:text-zinc-300",
                                )}
                              >
                                {t}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
              </div>
            </div>
          </aside>
        )}

        <section className="flex min-h-0 flex-col rounded-3xl border border-zinc-700/50 bg-zinc-800/55 xl:order-2">
          <div className="flex items-center justify-between border-b border-zinc-700/50 px-5 py-4">
            <h2 className="text-[2rem] font-normal tracking-tight">{centerTitle(studioView)}</h2>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setStudioView("dashboard")}
                className={cn(
                  "rounded-full px-3 py-1.5 text-xs transition-colors",
                  studioView === "dashboard" ? "bg-zinc-100 text-zinc-900" : "text-zinc-400 hover:bg-zinc-700/60",
                )}
              >
                Dashboard
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-auto p-4">
            {studioView === "dashboard" && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <MinimalStatCard label="Flashcards respondidos" value={flashcardsAnswered} tone="blue" />
                  <MinimalStatCard label="Quizzes feitos" value={quizAttempts} tone="emerald" />
                  <MinimalStatCard label="Tópicos estudados" value={studiedTopics.length} tone="violet" />
                </div>

                <div className="rounded-2xl border border-zinc-700/60 bg-zinc-900/55 p-4">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-zinc-500">Atividade diária</p>
                      <p className="text-sm text-zinc-300">Últimos 14 dias</p>
                    </div>
                    <span className="rounded-full bg-blue-500/15 px-3 py-1 text-xs text-blue-300">
                      Hoje: {doneToday}
                    </span>
                  </div>
                  <div className="h-44 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={dailyActivity} barCategoryGap="30%">
                        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                        <XAxis dataKey="label" stroke="#52525b" tickLine={false} axisLine={false} fontSize={11} />
                        <Tooltip
                          cursor={{ fill: "rgba(113,113,122,0.1)" }}
                          contentStyle={{
                            backgroundColor: "#18181b",
                            border: "1px solid #3f3f46",
                            borderRadius: "0.75rem",
                            color: "#e4e4e7",
                            fontSize: 12,
                          }}
                        />
                        <Bar dataKey="flash" name="Flashcards" stackId="a" fill="#7aa2ff" radius={[0, 0, 0, 0]} />
                        <Bar dataKey="quiz" name="Quiz" stackId="a" fill="#a78bfa" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-2 flex gap-4">
                    <span className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <span className="h-2 w-3 rounded-sm bg-blue-400/80" /> Flashcards
                    </span>
                    <span className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <span className="h-2 w-3 rounded-sm bg-violet-400/80" /> Quiz
                    </span>
                  </div>
                </div>

              </div>
            )}

            {studioView === "flashcards" && (
              <div className="space-y-4">
                {studyDeck.length > 0 ? (
                  <InlineFlashcardPlayer
                    subjectId={subjectId}
                    card={studyDeck[cardIdx]}
                    current={cardIdx + 1}
                    total={studyDeck.length}
                    showBack={showBack}
                    saving={savingResult}
                    onToggleSide={() => setShowBack((v) => !v)}
                    onPrev={() => {
                      if (cardIdx > 0) { setCardIdx((v) => v - 1); setShowBack(false) }
                    }}
                    onNext={() => {
                      if (cardIdx + 1 < studyDeck.length) { setCardIdx((v) => v + 1); setShowBack(false) }
                    }}
                    onAgain={() => handleStudyResult("again")}
                    onHard={() => handleStudyResult("hard")}
                    onGood={() => handleStudyResult("good")}
                    onEasy={() => handleStudyResult("easy")}
                    isSavedForLater={Boolean(studyDeck[cardIdx]?.favorite)}
                    onToggleSaveForLater={() => handleToggleFlashcardSaved(studyDeck[cardIdx])}
                    onOpenInPreview={(file, page, query) => openPreviewAtReference(file, page, query)}
                    onBackToDashboard={() => {
                      setStudyDeck([])
                      setCardIdx(0)
                      setShowBack(false)
                      setSessionDone(0)
                    }}
                  />
                ) : sessionDone > 0 ? (
                  /* Session complete screen */
                  <div className="rounded-3xl border border-emerald-500/30 bg-emerald-500/5 px-8 py-12 text-center">
                    <p className="text-5xl mb-4">✅</p>
                    <p className="text-2xl font-medium text-zinc-100 mb-1">Sessão concluída!</p>
                    <p className="text-zinc-400 mb-8">{sessionDone} {sessionDone === 1 ? "cartão revisto" : "cartões revistos"}.</p>
                    <div className="flex flex-wrap justify-center gap-3">
                      <Button onClick={() => setSessionDone(0)}>
                        Nova sessão
                      </Button>
                      <Button
                        variant="outline"
                        className="border-zinc-700 bg-transparent text-zinc-200 hover:bg-zinc-700/40"
                        onClick={startDueSession}
                      >
                        Rever pendentes ({srs?.due ?? 0})
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Performance stats */}
                    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                      <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/40 p-4">
                        <p className="text-3xl font-semibold leading-none text-zinc-100">{flashcardsAnswered}</p>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-zinc-500">Respondidas</p>
                      </div>
                      <div className="rounded-2xl border border-blue-500/30 bg-blue-500/8 p-4">
                        <p className="text-3xl font-semibold leading-none text-blue-300">{reviewedCount}</p>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-blue-400/70">Cartões revistos</p>
                      </div>
                      <div className="rounded-2xl border border-violet-500/30 bg-violet-500/8 p-4">
                        <p className="text-3xl font-semibold leading-none text-violet-300">{avgEase}</p>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-violet-400/70">Facilidade média</p>
                      </div>
                      <div className={cn(
                        "rounded-2xl border p-4",
                        (srs?.due ?? 0) > 0
                          ? "border-amber-500/40 bg-amber-500/10"
                          : "border-zinc-700/50 bg-zinc-800/40"
                      )}>
                        <p className={cn("text-3xl font-semibold leading-none", (srs?.due ?? 0) > 0 ? "text-amber-300" : "text-zinc-100")}>
                          {srs?.due ?? 0}
                        </p>
                        <p className={cn("mt-2 text-[11px] uppercase tracking-[0.12em]", (srs?.due ?? 0) > 0 ? "text-amber-400/70" : "text-zinc-500")}>
                          Para rever
                        </p>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-zinc-700/60 bg-zinc-900/55 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-zinc-500">Dificuldade dos cartões</p>
                        <span className="text-xs text-zinc-500">{completionPct}% do baralho revisto</span>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                          <p className="text-xl font-semibold text-amber-300">{difficultCards}</p>
                          <p className="text-[10px] uppercase tracking-[0.12em] text-amber-400/80">Difíceis</p>
                        </div>
                        <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 px-3 py-2">
                          <p className="text-xl font-semibold text-blue-300">{mediumCards}</p>
                          <p className="text-[10px] uppercase tracking-[0.12em] text-blue-400/80">Médios</p>
                        </div>
                        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2">
                          <p className="text-xl font-semibold text-emerald-300">{easyCards}</p>
                          <p className="text-[10px] uppercase tracking-[0.12em] text-emerald-400/80">Fáceis</p>
                        </div>
                      </div>
                    </div>

                    {/* Primary CTAs */}
                    <div className="flex flex-wrap items-center gap-3">
                      {(srs?.due ?? 0) > 0 && (
                        <button
                          onClick={startDueSession}
                          className="flex h-11 items-center gap-2 rounded-full bg-amber-500/20 px-6 text-sm font-semibold text-amber-300 ring-1 ring-amber-500/40 transition-colors hover:bg-amber-500/30"
                        >
                          Rever pendentes ({srs!.due})
                        </button>
                      )}
                      {savedFlashcards > 0 && (
                        <button
                          onClick={startSavedFlashcardsSession}
                          className="flex h-11 items-center gap-2 rounded-full bg-violet-500/20 px-6 text-sm font-semibold text-violet-300 ring-1 ring-violet-500/40 transition-colors hover:bg-violet-500/30"
                        >
                          Rever guardados ({savedFlashcards})
                        </button>
                      )}
                      {/* Inline card count stepper */}
                      <div className="flex items-center gap-1 rounded-full bg-zinc-800 px-1.5 py-1 ring-1 ring-zinc-700/50">
                        <button
                          onClick={() => setNCards(Math.max(1, nCards - 1))}
                          className="flex h-7 w-7 items-center justify-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
                        >−</button>
                        <span className="w-7 text-center text-sm font-semibold text-zinc-200">{nCards}</span>
                        <button
                          onClick={() => setNCards(Math.min(50, nCards + 1))}
                          className="flex h-7 w-7 items-center justify-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
                        >+</button>
                      </div>
                      <Button className="gap-2 px-6" onClick={handleGenerateFlashcards} disabled={generatingCards}>
                        <Sparkles className="h-3.5 w-3.5" />
                        {generatingCards
                          ? studyDeck.length > 0
                            ? `${studyDeck.length} / ${nCards}…`
                            : "A gerar…"
                          : (srs?.total ?? 0) === 0 ? "Gerar primeiros cartões" : "Gerar mais cartões"}
                      </Button>
                      {(srs?.total ?? 0) > 0 && (
                        <button
                          onClick={async () => {
                            if (!confirm(`Eliminar todos os ${srs!.total} cartões? Esta ação não pode ser revertida.`)) return
                            await api.flashcards.clearAll(subjectId)
                            await Promise.all([refetchDeck(), refetchProgress()])
                          }}
                          className="ml-auto text-xs text-zinc-600 transition-colors hover:text-red-400"
                        >
                          Limpar baralho
                        </button>
                      )}
                    </div>

                    {flashcardMsg && <p className="text-sm text-red-400">{flashcardMsg}</p>}

                    {/* Settings */}
                    <div className="rounded-2xl border border-zinc-700/60 bg-zinc-900/55 p-4">
                      <p className="mb-3 text-[11px] uppercase tracking-[0.16em] text-zinc-500">Tópico</p>
                      <MultiTopicDropdown
                        values={flashcardTopics}
                        onChange={setFlashcardTopics}
                        options={sortedTopics}
                        allLabel="Todos os topicos"
                      />
                    </div>

                    {/* Anki export */}
                    {(srs?.total ?? 0) > 0 && (
                      <button
                        onClick={handleExportAnki}
                        className="flex items-center gap-1.5 self-start rounded-full px-4 py-2 text-xs font-medium text-zinc-500 ring-1 ring-zinc-700/40 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
                      >
                        <Download className="h-3 w-3" />
                        Exportar para Anki ({srs!.total} cartões)
                      </button>
                    )}
                  </>
                )}
              </div>
            )}

            {studioView === "quiz" && (
              <div className="space-y-4">
                {quizPhase === "config" && (
                  <>
                    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                      <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/40 p-4">
                        <p className="text-3xl font-semibold leading-none text-zinc-100">{quizQuestionsAnswered}</p>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-zinc-500">Perguntas respondidas</p>
                      </div>
                      <div className="rounded-2xl border border-blue-500/30 bg-blue-500/8 p-4">
                        <p className="text-3xl font-semibold leading-none text-blue-300">{quizAccuracyPct}%</p>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-blue-400/70">Acerto global</p>
                      </div>
                      <div className="rounded-2xl border border-violet-500/30 bg-violet-500/8 p-4">
                        <p className="text-3xl font-semibold leading-none text-violet-300">{quizAttempts}</p>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-violet-400/70">Tentativas</p>
                      </div>
                      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/8 p-4 col-span-2 lg:col-span-1">
                        <p className="text-3xl font-semibold leading-none text-amber-300">{savedQuizQuestions.length}</p>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-amber-400/70">Guardadas</p>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-zinc-700/60 bg-zinc-900/55 p-4">
                      <p className="mb-3 text-[11px] uppercase tracking-[0.16em] text-zinc-500">Âmbito</p>
                      <div className="mb-4">
                        <MultiTopicDropdown
                          values={quizTopics}
                          onChange={setQuizTopics}
                          options={sortedTopics}
                          allLabel="Todos os topicos"
                        />
                      </div>
                      <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-zinc-500">Dificuldade</p>
                      <div className="mb-4 flex flex-wrap gap-2">
                        {["Fácil", "Médio", "Difícil"].map((d) => (
                          <TopicChip key={d} label={d} active={quizDifficulty === d} onClick={() => setQuizDifficulty(d)} />
                        ))}
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <div className="flex items-center gap-1 rounded-full bg-zinc-800 px-1.5 py-1 ring-1 ring-zinc-700/50">
                        <button
                          onClick={() => setQuizN(Math.max(1, quizN - 1))}
                          className="flex h-7 w-7 items-center justify-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
                        >
                          −
                        </button>
                        <span className="w-7 text-center text-sm font-semibold text-zinc-200">{quizN}</span>
                        <button
                          onClick={() => setQuizN(Math.min(50, quizN + 1))}
                          className="flex h-7 w-7 items-center justify-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
                        >
                          +
                        </button>
                      </div>
                      <Button className="gap-2 px-6" onClick={handleGenerateQuiz} disabled={generatingQuiz}>
                        <Layers3 className="h-3.5 w-3.5" />
                        {generatingQuiz
                          ? quizQuestions.length > 0
                            ? `${quizQuestions.length} / ${quizN} questões…`
                            : "A gerar…"
                          : "Gerar Questionário"}
                      </Button>
                      {savedQuizQuestions.length > 0 && (
                        <button
                          onClick={() => {
                            setQuizQuestions(savedQuizQuestions)
                            setQuizFinalAnswers([])
                            setQuizPhase("taking")
                          }}
                          className="rounded-full border border-violet-500/40 bg-violet-500/10 px-5 py-2 text-sm font-semibold text-violet-300 transition-colors hover:bg-violet-500/20"
                        >
                          Rever guardadas ({savedQuizQuestions.length})
                        </button>
                      )}
                    </div>
                    {quizMsg && <p className="text-sm text-red-400">{quizMsg}</p>}

                    {quizHistory.length > 0 && (
                      <div className="rounded-2xl border border-zinc-700/60 bg-zinc-900/55 p-4">
                        <p className="mb-3 text-[11px] uppercase tracking-[0.16em] text-zinc-500">Perguntas por tópico</p>
                        {quizTopicBreakdown.length > 0 ? (
                          <div className="h-52 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                              <BarChart data={quizTopicBreakdown} barCategoryGap="28%">
                                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                                <XAxis
                                  dataKey="topic"
                                  stroke="#52525b"
                                  tickLine={false}
                                  axisLine={false}
                                  fontSize={11}
                                  tickFormatter={(value) => String(value).slice(0, 18)}
                                />
                                <Tooltip
                                  cursor={{ fill: "rgba(113,113,122,0.1)" }}
                                  contentStyle={{
                                    backgroundColor: "#18181b",
                                    border: "1px solid #3f3f46",
                                    borderRadius: "0.75rem",
                                    color: "#e4e4e7",
                                    fontSize: 12,
                                  }}
                                />
                                <Bar dataKey="total" name="Perguntas" fill="#7aa2ff" radius={[6, 6, 0, 0]} />
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        ) : (
                          <p className="text-sm text-zinc-500">Ainda sem dados por tópico.</p>
                        )}
                      </div>
                    )}
                  </>
                )}

                {quizPhase === "taking" && quizQuestions.length > 0 && (
                  <QuizPlayer
                    questions={quizQuestions}
                    subjectId={subjectId}
                    loadingMore={generatingQuiz}
                    savedQuestionKeys={new Set(savedQuizQuestions.map(getQuizQuestionKey))}
                    onToggleSaveForLater={handleToggleSavedQuizQuestion}
                    onOpenInPreview={(file, page, query) => openPreviewAtReference(file, page, query)}
                    onFinish={async (answers) => {
                      const score = answers.filter((a) => a.isCorrect).length
                      const selectedTopics = quizTopics.filter((t) => sortedTopics.includes(t))
                      const quizTopic =
                        selectedTopics.length > 0
                          ? selectedTopics.join(", ")
                          : topic === "Toda a UC"
                            ? subject!.name
                            : topic
                      await api.quiz.saveResult(subjectId, quizTopic, score, quizQuestions.length)
                      setQuizFinalAnswers(answers)
                      setQuizPhase("results")
                      await refetchProgress()
                    }}
                  />
                )}

                {quizPhase === "results" && (
                  <>
                    <div className="rounded-3xl border border-zinc-700/60 bg-zinc-900/55 p-8 text-center">
                      {(() => {
                        const correct = quizFinalAnswers.filter((a) => a.isCorrect).length
                        const pct = Math.round((correct / quizQuestions.length) * 100)
                        return (
                          <>
                            <p className="text-5xl mb-3">🏁</p>
                            <p className="text-5xl font-bold mb-1">{correct}/{quizQuestions.length}</p>
                            <p className={cn("text-xl font-medium", pct >= 70 ? "text-emerald-400" : pct >= 40 ? "text-amber-400" : "text-red-400")}>
                              {pct}%
                            </p>
                            <p className="mt-3 text-sm text-zinc-500">
                              {pct >= 80 ? "Excelente!" : pct >= 60 ? "Bom trabalho!" : pct >= 40 ? "A melhorar." : "Continua a estudar!"}
                            </p>
                          </>
                        )
                      })()}
                    </div>

                    <div className="space-y-2">
                      {quizQuestions.map((q, i) => {
                        const ans = quizFinalAnswers[i]
                        return (
                          <div
                            key={i}
                            className={cn(
                              "flex items-start gap-3 rounded-xl border px-4 py-3",
                              ans?.isCorrect ? "border-emerald-500/25 bg-emerald-500/5" : "border-red-500/25 bg-red-500/5",
                            )}
                          >
                            <span className="mt-0.5 shrink-0 text-base">{ans?.isCorrect ? "✓" : "✗"}</span>
                            <div className="min-w-0 flex-1">
                              <p className="text-sm text-zinc-300 line-clamp-2">{q.pergunta}</p>
                              {!ans?.isCorrect && (
                                <p className="mt-1 text-xs text-emerald-400">Correto: {q.opcoes[q.correta]}</p>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>

                    <div className="flex flex-wrap gap-3">
                      <button
                        onClick={() => { setQuizFinalAnswers([]); setQuizPhase("taking") }}
                        className="rounded-full border border-zinc-700 px-5 py-2 text-sm text-zinc-200 transition-colors hover:bg-zinc-800"
                      >
                        Repetir quiz
                      </button>
                      <button
                        onClick={() => { setQuizFinalAnswers([]); setQuizPhase("config") }}
                        className="rounded-full bg-zinc-100 px-5 py-2 text-sm font-medium text-zinc-900 transition-colors hover:bg-white"
                      >
                        Nova configuração
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {studioView === "qa" && (
              <div className="space-y-4">
                <div className="rounded-3xl border border-zinc-700 bg-zinc-900/55 p-4">
                  <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-zinc-500">Q&A</p>
                  <p className="text-sm text-zinc-400">
                    Faz perguntas sobre as tuas fontes e navega para as páginas citadas.
                  </p>
                  {topics.length > 0 && (
                    <div className="mt-3">
                      <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-zinc-500">Filtrar por tópico</p>
                      <TopicDropdown
                        value={topic}
                        onChange={setTopic}
                        options={sortedTopics}
                        allLabel="Todos os tópicos"
                      />
                    </div>
                  )}
                </div>
                <Textarea
                  rows={4}
                  value={qaQuestion}
                  onChange={(e) => setQaQuestion(e.target.value)}
                  placeholder="Escreve a tua pergunta..."
                  className="rounded-2xl border-zinc-700 bg-zinc-900/65 text-zinc-100"
                />
                <div className="flex flex-wrap gap-3">
                  <Button className="gap-2 px-6" onClick={handleAskQa} disabled={askingQa}>
                    <MessageSquare className="h-3.5 w-3.5" /> {askingQa ? "A perguntar..." : "Perguntar"}
                  </Button>
                </div>
                {qaMsg && <p className="text-sm text-zinc-300">{qaMsg}</p>}
                {qaAnswer && (
                  <div className="space-y-3 rounded-3xl border border-zinc-700 bg-zinc-900/55 p-4">
                    <p className="text-sm leading-relaxed text-zinc-100 whitespace-pre-wrap">{qaAnswer}</p>
                    {qaSources.length > 0 && (
                      <div>
                        <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-zinc-500">Fontes</p>
                        <div className="flex flex-wrap gap-2">
                          {qaSources.map((s, idx) => (
                            <button
                              key={`${s.file}-${s.page}-${idx}`}
                              onClick={() => openPreviewAtReference(s.file, s.page, qaQuestion)}
                              className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300 hover:bg-zinc-700"
                            >
                              {s.file} - Pag. {s.page}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {studioView === "summary" && (
              <TopicSummaryView
                subjectId={subjectId}
                topics={topics}
                topicSummaries={subject.topic_summaries ?? {}}
                selectedTopic={summaryTopic ?? [...topics].sort((a, b) => a.localeCompare(b, "pt"))[0] ?? null}
                onSelectTopic={setSummaryTopic}
                onRefreshDone={() => qc.invalidateQueries({ queryKey: ["subjects", subjectId] })}
              />
            )}

            {studioView === "notes" && (
              <div className="space-y-4">
                <RichNotesEditor
                  value={quickNotes}
                  onChange={setQuickNotes}
                  placeholder="Escreve notas da UC aqui..."
                />
                <p className="text-xs text-zinc-500">Nota: estas notas são locais nesta sessão por enquanto.</p>
              </div>
            )}

            {studioView === "preview" && (
              <div className="flex h-full flex-col gap-3">
                {/* File selector */}
                {previewableFiles.length > 0 ? (
                  <>
                    {previewableFiles.length > 1 && (
                      <div className="flex flex-wrap gap-2">
                        {previewableFiles.map((f) => (
                          <button
                            key={f.name}
                            onClick={() => { setSelectedFile(f.name); setViewerPage(undefined); setPreviewReference(null) }}
                            className={cn(
                              "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors",
                              selectedFile === f.name
                                ? "border-blue-500/50 bg-blue-500/15 text-blue-300"
                                : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200",
                            )}
                          >
                            <FileText className="h-3 w-3" />
                            <span className="max-w-[180px] truncate">{f.name}</span>
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="relative flex-1 min-h-[480px] overflow-hidden rounded-2xl border border-zinc-700/60">
                      {previewReference?.file === selectedFile && previewReference?.page && (
                        <PreviewReferenceHighlight
                          subjectId={subjectId}
                          file={previewReference.file}
                          page={previewReference.page}
                          query={previewReference.query ?? ""}
                        />
                      )}
                      {pdfLoading && (
                        <div className="flex h-full items-center justify-center text-zinc-500 text-sm" style={{ minHeight: "480px" }}>
                          A carregar PDF…
                        </div>
                      )}
                      {!pdfLoading && pdfFrameUrl ? (
                        <>
                          <iframe
                            key={pdfFrameUrl}
                            title="PDF preview"
                            src={pdfFrameUrl}
                            className="h-full w-full bg-zinc-950"
                            style={{ minHeight: "480px" }}
                          />
                          <a
                            href={viewerUrl ?? "#"}
                            target="_blank"
                            rel="noreferrer"
                            className="absolute bottom-3 right-3 rounded-full border border-zinc-600 bg-zinc-900/80 px-3 py-1 text-[11px] text-zinc-400 backdrop-blur-sm hover:border-zinc-400 hover:text-zinc-200"
                          >
                            Abrir em nova aba ↗
                          </a>
                        </>
                      ) : !pdfLoading && pdfLoadError ? (
                        <div className="flex h-full flex-col items-center justify-center gap-2 text-zinc-500 text-sm" style={{ minHeight: "480px" }}>
                          <span>Não foi possível carregar o PDF.</span>
                          <a href={viewerUrl ?? "#"} target="_blank" rel="noreferrer" className="text-xs text-blue-400 hover:underline">Abrir em nova aba ↗</a>
                        </div>
                      ) : !pdfLoading && (
                        <div className="flex h-full items-center justify-center text-zinc-500" style={{ minHeight: "480px" }}>
                          Seleciona um ficheiro para visualizar.
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-zinc-700 py-16 text-center">
                    <FileText className="h-10 w-10 text-zinc-600" />
                    <div>
                      <p className="text-sm font-medium text-zinc-300">Sem ficheiros PDF</p>
                      <p className="mt-1 text-xs text-zinc-500">Adiciona fontes para poder visualizar aqui.</p>
                    </div>
                    <button
                      onClick={() => {
                        setUploadOpen(true)
                      }}
                      className="mt-1 rounded-full border border-zinc-700 px-4 py-1.5 text-xs text-zinc-300 transition-colors hover:bg-zinc-800"
                    >
                      Adicionar ficheiros →
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        <aside className="flex min-h-0 flex-col rounded-3xl border border-zinc-700/50 bg-zinc-800/55 xl:order-1">
          <div className="flex items-center justify-between border-b border-zinc-700/50 px-5 py-4">
            <h2 className="text-[2rem] font-normal tracking-tight">Estúdio</h2>
          </div>

          <div className="grid grid-cols-2 gap-2 p-4">
            <FeatureTile label="Dashboard" icon={BarChart3} active={studioView === "dashboard"} onClick={() => setStudioView("dashboard")} />
            <FeatureTile label="Resumo" icon={BookOpen} active={studioView === "summary"} onClick={() => setStudioView("summary")} />
            <FeatureTile label="Questionário" icon={Layers3} active={studioView === "quiz"} onClick={() => setStudioView("quiz")} />
            <FeatureTile label="Cartões" icon={Sparkles} active={studioView === "flashcards"} onClick={() => setStudioView("flashcards")} badge={srs?.due ?? 0} />
            <FeatureTile label="Q&A" icon={MessageSquare} active={studioView === "qa"} onClick={() => setStudioView("qa")} />
            <FeatureTile label="Notas" icon={FileText} active={studioView === "notes"} onClick={() => setStudioView("notes")} />
          </div>

        </aside>
      </div>
    </div>
  )
}

// ── Per-topic summary view ─────────────────────────────────────────────────────

function parseSummarySection(text: string, heading: string): string {
  const re = new RegExp(`\\*\\*${heading}:\\*\\*\\s*([\\s\\S]*?)(?=\\*\\*[^*]+:\\*\\*|$)`, "i")
  const m = text.match(re)
  return m ? m[1].trim() : ""
}

function SummarySection({
  title,
  content,
  colorClass,
  icon,
}: {
  title: string
  content: string
  colorClass: string
  icon: React.ReactNode
}) {
  if (!content) return null
  const bullets = content
    .split("\n")
    .map((l) => l.replace(/^[•\-*]\s*/, "").trim())
    .filter(Boolean)
  const isBullets = bullets.length > 1
  return (
    <div className={cn("rounded-2xl p-4", colorClass)}>
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-black/20 text-[13px]">{icon}</span>
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-80">{title}</p>
      </div>
      {isBullets ? (
        <ul className="space-y-1.5">
          {bullets.map((b, i) => (
            <li key={i} className="flex items-start gap-2 text-sm leading-relaxed">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-60" />
              {b}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm leading-relaxed">{content}</p>
      )}
    </div>
  )
}

function TopicDropdown({
  value,
  onChange,
  options,
  allLabel = "Todos os tópicos",
  summaryStateMap,
}: {
  value: string
  onChange: (v: string) => void
  options: string[]
  allLabel?: string | undefined
  summaryStateMap?: Record<string, string>
}) {
  const sorted = [...options].sort((a, b) => a.localeCompare(b, "pt"))
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-xl border border-zinc-700 bg-zinc-900/70 px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
    >
      {allLabel !== undefined && <option value="Toda a UC">{allLabel}</option>}
      {sorted.map((t) => (
        <option key={t} value={t}>
          {summaryStateMap ? `${summaryStateMap[t] ? "✓" : "○"} ${t}` : t}
        </option>
      ))}
    </select>
  )
}

function MultiTopicDropdown({
  values,
  onChange,
  options,
  allLabel = "Todos os topicos",
}: {
  values: string[]
  onChange: (next: string[]) => void
  options: string[]
  allLabel?: string
}) {
  const sorted = [...options].sort((a, b) => a.localeCompare(b, "pt"))
  const selected = new Set(values.filter((v) => sorted.includes(v)))
  const selectedCount = selected.size
  const buttonLabel =
    selectedCount === 0
      ? allLabel
      : selectedCount <= 2
        ? Array.from(selected).join(", ")
        : `${selectedCount} topicos`

  function toggle(topic: string) {
    const next = new Set(selected)
    if (next.has(topic)) next.delete(topic)
    else next.add(topic)
    onChange(sorted.filter((t) => next.has(t)))
  }

  return (
    <details className="group relative w-full">
      <summary className="list-none w-full cursor-pointer rounded-xl border border-zinc-700 bg-zinc-900/70 px-3 py-2 text-left text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500/50">
        {buttonLabel}
      </summary>
      <div className="absolute z-20 mt-2 w-full rounded-xl border border-zinc-700 bg-zinc-900 p-2 shadow-xl">
        <button
          type="button"
          onClick={() => onChange([])}
          className="mb-2 w-full rounded-lg border border-zinc-700 px-2 py-1.5 text-left text-xs text-zinc-300 transition-colors hover:bg-zinc-800"
        >
          {allLabel}
        </button>
        <div className="max-h-52 overflow-auto pr-1">
          {sorted.map((topic) => (
            <label
              key={topic}
              className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-800"
            >
              <input
                type="checkbox"
                checked={selected.has(topic)}
                onChange={() => toggle(topic)}
                className="h-3.5 w-3.5 rounded border-zinc-600 bg-zinc-800 text-blue-500"
              />
              <span className="truncate">{topic}</span>
            </label>
          ))}
        </div>
      </div>
    </details>
  )
}

function RichNotesEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  const editorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!editorRef.current) return
    if (editorRef.current.innerHTML !== value) {
      editorRef.current.innerHTML = value
    }
  }, [value])

  function run(command: string, arg?: string) {
    if (!editorRef.current) return
    editorRef.current.focus()
    document.execCommand("styleWithCSS", false, "true")
    document.execCommand(command, false, arg)
    onChange(editorRef.current.innerHTML)
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-700/60 bg-zinc-900/65">
      <div className="flex flex-wrap items-center gap-1 border-b border-zinc-700/60 bg-zinc-900/90 p-2">
        <button onClick={() => run("bold")} className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800">B</button>
        <button onClick={() => run("italic")} className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800">I</button>
        <button onClick={() => run("underline")} className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800">U</button>
        <span className="mx-1 h-5 w-px bg-zinc-700" />
        <button onClick={() => run("insertUnorderedList")} className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800">• Lista</button>
        <button onClick={() => run("insertOrderedList")} className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800">1. Lista</button>
        <span className="mx-1 h-5 w-px bg-zinc-700" />
        <button onClick={() => run("formatBlock", "H2")} className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800">Título</button>
        <button onClick={() => run("formatBlock", "P")} className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800">Texto</button>
        <select
          defaultValue="3"
          onChange={(e) => run("fontSize", e.target.value)}
          className="ml-1 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-300"
        >
          <option value="2">Pequeno</option>
          <option value="3">Normal</option>
          <option value="4">Médio</option>
          <option value="5">Grande</option>
        </select>
        <span className="mx-1 h-5 w-px bg-zinc-700" />
        <button onClick={() => run("removeFormat")} className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800">Limpar</button>
      </div>

      <div
        ref={editorRef}
        contentEditable
        suppressContentEditableWarning
        onInput={() => onChange(editorRef.current?.innerHTML ?? "")}
        data-placeholder={placeholder ?? ""}
        className="min-h-[380px] p-4 text-sm leading-relaxed text-zinc-100 outline-none [&[data-placeholder]:empty:before]:text-zinc-500 [&[data-placeholder]:empty:before]:content-[attr(data-placeholder)]"
      />
    </div>
  )
}

function TopicSummaryView({
  subjectId,
  topics,
  topicSummaries,
  selectedTopic,
  onSelectTopic,
  onRefreshDone,
}: {
  subjectId: string
  topics: string[]
  topicSummaries: Record<string, string>
  selectedTopic: string | null
  onSelectTopic: (t: string) => void
  onRefreshDone: () => void
}) {
  const [refreshing, setRefreshing] = useState(false)

  const missingCount = topics.filter((t) => !topicSummaries[t]).length

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await api.subjects.refreshSummaries(subjectId)
      // Poll until all summaries arrive (max ~2 min)
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        onRefreshDone()
        if (attempts >= 24) { clearInterval(poll); setRefreshing(false) }
      }, 5000)
    } catch {
      setRefreshing(false)
    }
  }

  if (topics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
        <BookOpen className="h-10 w-10 text-zinc-600" />
        <p className="text-sm text-zinc-500">Sem tópicos ainda. Adiciona ficheiros para gerar resumos automáticos.</p>
      </div>
    )
  }

  const raw = selectedTopic ? (topicSummaries[selectedTopic] ?? "") : ""
  const intro = parseSummarySection(raw, "Introdução")
  const pontos = parseSummarySection(raw, "Pontos-chave")
  const perolas = parseSummarySection(raw, "Pérolas Clínicas")
  const sortedTopics = [...topics].sort((a, b) => a.localeCompare(b, "pt"))

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="rounded-2xl border border-zinc-700/60 bg-zinc-900/50 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-[11px] uppercase tracking-[0.16em] text-zinc-500">Resumo por tópico</p>
          {missingCount > 0 && (
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              title={`Gerar resumos em falta (${missingCount})`}
              className="shrink-0 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:border-blue-500/50 hover:text-blue-300 disabled:opacity-50"
            >
              {refreshing ? "A gerar…" : `Gerar ${missingCount}`}
            </button>
          )}
        </div>
        <TopicDropdown
          value={selectedTopic ?? sortedTopics[0]}
          onChange={onSelectTopic}
          options={sortedTopics}
          allLabel={undefined}
          summaryStateMap={topicSummaries}
        />
      </div>

      {/* Summary content */}
      {selectedTopic && (
        <div className="flex-1 overflow-auto">
          {!raw ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-blue-400" />
              <p className="text-sm text-zinc-500">
                {refreshing ? "A gerar resumo…" : "Resumo em falta — clica «Gerar» acima."}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="mb-2">
                <h3 className="text-lg font-medium text-zinc-100">{selectedTopic}</h3>
              </div>
              <SummarySection
                title="Introdução"
                icon="📖"
                colorClass="border border-blue-500/20 bg-blue-500/8 text-blue-100"
                content={intro}
              />
              <SummarySection
                title="Pontos-chave"
                icon="✦"
                colorClass="border border-teal-500/20 bg-teal-500/8 text-teal-100"
                content={pontos}
              />
              <SummarySection
                title="Pérolas Clínicas"
                icon="💎"
                colorClass="border border-amber-500/20 bg-amber-500/8 text-amber-100"
                content={perolas}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PreviewReferenceHighlight({
  subjectId,
  file,
  page,
  query,
}: {
  subjectId: string
  file: string
  page: number
  query: string
}) {
  const [texts, setTexts] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    api.subjects.sourceText(subjectId, file, page)
      .then((r) => { if (!cancelled) setTexts(r.texts) })
      .catch(() => {
        if (cancelled) return
        setTexts([])
        setError("Não foi possível carregar o excerto da referência.")
      })
    return () => { cancelled = true }
  }, [subjectId, file, page])

  if (error) {
    return (
      <div className="absolute left-3 right-3 top-3 z-10 rounded-2xl border border-amber-500/30 bg-zinc-950/85 px-4 py-3 text-xs text-amber-300 backdrop-blur-sm">
        {error}
      </div>
    )
  }
  if (texts.length === 0) return null

  return (
    <div className="absolute left-3 right-3 top-3 z-10 rounded-2xl border border-amber-500/30 bg-zinc-950/85 px-4 py-3 text-xs text-zinc-300 backdrop-blur-sm">
      <p className="mb-2 text-[10px] uppercase tracking-[0.14em] text-amber-400/80">Excerto da referência · Pág. {page}</p>
      <div className="max-h-24 space-y-1.5 overflow-auto pr-1">
        {texts.slice(0, 2).map((t, i) => (
          <p key={i} dangerouslySetInnerHTML={{ __html: highlightKeywords(t, query) }} />
        ))}
      </div>
    </div>
  )
}

function InlineFlashcardPlayer({
  subjectId,
  card,
  current,
  total,
  showBack,
  saving,
  onToggleSide,
  onPrev,
  onNext,
  onAgain,
  onHard,
  onGood,
  onEasy,
  isSavedForLater,
  onToggleSaveForLater,
  onOpenInPreview,
  onBackToDashboard,
}: {
  subjectId: string
  card: FlashcardInDB
  current: number
  total: number
  showBack: boolean
  saving: boolean
  onToggleSide: () => void
  onPrev: () => void
  onNext: () => void
  onAgain: () => void
  onHard: () => void
  onGood: () => void
  onEasy: () => void
  isSavedForLater: boolean
  onToggleSaveForLater: () => void
  onOpenInPreview: (file: string, page?: number, query?: string) => void
  onBackToDashboard: () => void
}) {
  const [showReference, setShowReference] = useState(false)
  const progressPct = (current / total) * 100
  const reference = parseCardReference(card.fonte)
  const fetchUrl = reference ? `/api/files/${subjectId}/${encodeURIComponent(reference.file)}` : null

  // Source text excerpt for the reference panel
  const [sourceTexts, setSourceTexts] = useState<string[]>([])
  const [sourceTextError, setSourceTextError] = useState<string | null>(null)
  useEffect(() => {
    if (!showReference || !reference?.file || !reference?.page) {
      setSourceTexts([])
      setSourceTextError(null)
      return
    }
    setSourceTextError(null)
    api.subjects.sourceText(subjectId, reference.file, reference.page)
      .then((r) => setSourceTexts(r.texts))
      .catch(() => {
        setSourceTexts([])
        setSourceTextError("Não foi possível carregar o excerto da fonte.")
      })
  }, [showReference, reference?.file, reference?.page, subjectId])

  // Keyboard shortcuts: Space/Enter = flip | 1-4 = rate (only when back shown)
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); onToggleSide() }
      if (!showBack) return
      if (e.key === "1") onAgain()
      if (e.key === "2") onHard()
      if (e.key === "3") onGood()
      if (e.key === "4") onEasy()
    }
    window.addEventListener("keydown", handleKey)
    return () => window.removeEventListener("keydown", handleKey)
  }, [showBack, onToggleSide, onAgain, onHard, onGood, onEasy])

  return (
    <div className="space-y-5">
      <div className="flex justify-end">
        <button
          onClick={onBackToDashboard}
          className="rounded-full border border-zinc-700 px-4 py-1.5 text-xs text-zinc-300 transition-colors hover:bg-zinc-800"
        >
          Voltar ao painel de flashcards
        </button>
      </div>
      {/* Card row: prev | card | next */}
      <div className="flex items-center gap-3">
        <CircleNav onClick={onPrev} disabled={current === 1}>←</CircleNav>

        <div className="min-w-0 flex-1" style={{ perspective: "1200px" }}>
          <motion.div
            animate={{ rotateY: showBack ? 180 : 0 }}
            transition={{ type: "spring", stiffness: 280, damping: 28 }}
            style={{ transformStyle: "preserve-3d", minHeight: "280px" }}
            className="relative w-full cursor-pointer"
            onClick={onToggleSide}
          >
            {/* Front face */}
            <div className="backface-hidden absolute inset-0 min-h-[280px] rounded-[2rem] border border-zinc-600/60 bg-zinc-900/80 px-8 py-7 hover:border-zinc-500/70 transition-colors">
              <p className="text-[11px] uppercase tracking-[0.14em] text-zinc-500 mb-5">Frente</p>
              <p className="text-3xl leading-snug tracking-tight text-zinc-100">
                {clozeToBlank(card.frente)}
              </p>
              <p className="mt-6 text-sm text-zinc-500">Espaço ou clique para revelar →</p>
            </div>

            {/* Back face */}
            <div
              className="backface-hidden absolute inset-0 min-h-[280px] rounded-[2rem] border border-blue-500/25 bg-zinc-900/80 px-8 py-7"
              style={{ transform: "rotateY(180deg)" }}
            >
              <p className="text-[11px] uppercase tracking-[0.14em] text-blue-400/70 mb-5">Verso</p>
              <p className="text-3xl leading-snug tracking-tight text-zinc-100">
                <span dangerouslySetInnerHTML={{ __html: clozeHighlight(card.verso) }} />
              </p>
              {card.fonte && (
                <p className="mt-5 text-xs text-zinc-500 truncate">📄 {card.fonte}</p>
              )}
            </div>
          </motion.div>
        </div>

        <CircleNav onClick={onNext} disabled={current === total}>→</CircleNav>
      </div>

      {/* Save for later + reference controls */}
      <div className="flex justify-center gap-2">
          <button
            onClick={onToggleSaveForLater}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-xs transition-colors",
              isSavedForLater
                ? "border-violet-500/50 bg-violet-500/15 text-violet-300"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200",
            )}
          >
            ⭐ {isSavedForLater ? "Guardado para depois" : "Guardar para depois"}
          </button>
          {reference && (
            <button
              onClick={() => setShowReference((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 px-4 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-200"
            >
              📄 {showReference ? "Esconder referência" : "Ver referência"}
            </button>
          )}
      </div>

      {/* Animated PDF reference panel — slides open below the card */}
      <motion.div
        animate={{
          height: showReference && reference ? (sourceTexts.length > 0 ? 700 : 500) : 0,
          opacity: showReference && reference ? 1 : 0,
        }}
        initial={{ height: 0, opacity: 0 }}
        transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
        className="overflow-hidden"
      >
        {reference && (
          <div className="space-y-2 pt-1">
            {/* Source text excerpt with keyword highlights */}
            {sourceTexts.length > 0 && (
              <div className="rounded-2xl border border-amber-500/25 bg-amber-500/5 px-4 py-3">
                <p className="text-[10px] uppercase tracking-[0.14em] text-amber-400/70 mb-2">Excerto da fonte · Pág. {reference.page}</p>
                <div className="space-y-2 max-h-48 overflow-auto">
                  {sourceTexts.map((t, i) => (
                    <p key={i} className="text-xs leading-relaxed text-zinc-300"
                      dangerouslySetInnerHTML={{ __html: highlightKeywords(t, card.frente + " " + card.verso) }}
                    />
                  ))}
                </div>
              </div>
            )}
            {sourceTextError && (
              <div className="rounded-2xl border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-xs text-amber-300">
                {sourceTextError}
              </div>
            )}
            <div className="flex justify-end">
              <button
                onClick={() => reference && onOpenInPreview(reference.file, reference.page, `${card.frente} ${card.verso}`)}
                className="rounded-full border border-zinc-700 px-3 py-1 text-[11px] text-zinc-300 transition-colors hover:bg-zinc-800"
              >
                Abrir no Preview
              </button>
            </div>
            {/* PDF viewer */}
            {fetchUrl && reference?.page && (
              <PdfPageViewer file={fetchUrl} page={reference.page} openUrl={fetchUrl} />
            )}
          </div>
        )}
      </motion.div>

      {/* SRS rating buttons — only appear after revealing the back */}
      <div className="mx-auto max-w-2xl">
        {showBack ? (
          <div className="space-y-2">
            <p className="text-center text-[11px] uppercase tracking-[0.16em] text-zinc-500">Como correu?</p>
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              <button
                onClick={onAgain}
                disabled={saving}
                className="h-11 rounded-full border border-red-500/40 bg-red-500/10 text-sm font-semibold text-red-400 transition-colors hover:bg-red-500/20 disabled:opacity-50"
              >
                {saving ? "…" : "1 · Outra vez"}
              </button>
              <button
                onClick={onHard}
                disabled={saving}
                className="h-11 rounded-full border border-orange-500/40 bg-orange-500/10 text-sm font-semibold text-orange-300 transition-colors hover:bg-orange-500/20 disabled:opacity-50"
              >
                2 · Difícil
              </button>
              <button
                onClick={onGood}
                disabled={saving}
                className="h-11 rounded-full border border-blue-500/40 bg-blue-500/10 text-sm font-semibold text-blue-300 transition-colors hover:bg-blue-500/20 disabled:opacity-50"
              >
                3 · Bom
              </button>
              <button
                onClick={onEasy}
                disabled={saving}
                className="h-11 rounded-full border border-emerald-500/40 bg-emerald-500/10 text-sm font-semibold text-emerald-300 transition-colors hover:bg-emerald-500/20 disabled:opacity-50"
              >
                4 · Fácil
              </button>
            </div>
          </div>
        ) : (
          <div className="h-[72px]" />
        )}
      </div>

      {/* Progress bar */}
      <div className="mx-auto flex max-w-2xl items-center gap-3 text-xs text-zinc-500">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-zinc-800">
          <div
            className="h-full rounded-full bg-blue-400 transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <span className="tabular-nums shrink-0">{current} / {total}</span>
      </div>
    </div>
  )
}

function parseCardReference(source: string | null | undefined): { file: string; page?: number } | null {
  if (!source) return null
  const trimmed = source.trim()
  if (!trimmed) return null

  const match = trimmed.match(/^(.*?)(?:,\s*P[áa]g\.?\s*(\d+))?$/i)
  if (!match) return null

  const file = match[1]?.trim()
  const page = match[2] ? Number(match[2]) : undefined
  if (!file) return null
  return { file, page }
}

/** Wraps keywords from `query` found in `text` with a yellow highlight span. */
function highlightKeywords(text: string, query: string): string {
  const words = Array.from(new Set(
    query.split(/\s+/)
      .map((w) => w.replace(/[^0-9A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF]/g, ""))
      .filter((w) => w.length >= 4)
  ))
  const escaped = escapeHtml(text)
  if (words.length === 0) return escaped
  return escaped.replace(
    new RegExp(`(${words.map(escapeRegex).map(escapeHtml).join("|")})`, "gi"),
    '<mark style="background:rgba(251,191,36,0.3);color:inherit;border-radius:2px;padding:0 1px">$1</mark>',
  )
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function CircleNav({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="grid h-16 w-16 place-items-center rounded-full border border-zinc-600 bg-zinc-900/80 text-3xl text-blue-400 transition-colors hover:bg-zinc-800 disabled:opacity-40"
    >
      {children}
    </button>
  )
}

function centerTitle(view: StudioView): string {
  switch (view) {
    case "dashboard":
      return "Painel de Estudo"
    case "flashcards":
      return "Flashcards"
    case "quiz":
      return "Questionário"
    case "qa":
      return "Q&A"
    case "summary":
      return "Resumo"
    case "notes":
      return "Notas"
    case "preview":
      return "Pré-visualização"
    default:
      return "Estúdio"
  }
}

function FeatureTile({
  label,
  icon: Icon,
  active,
  onClick,
  badge,
}: {
  label: string
  icon: React.ElementType
  active: boolean
  onClick: () => void
  badge?: number
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative rounded-2xl border px-3 py-3 text-left transition-colors",
        active
          ? "border-blue-500/40 bg-blue-500/10"
          : "border-zinc-700/60 bg-zinc-900/55 hover:border-zinc-600/60 hover:bg-zinc-700/40",
      )}
    >
      {badge != null && badge > 0 && (
        <span className="absolute right-2 top-2 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-zinc-900">
          {badge > 99 ? "99+" : badge}
        </span>
      )}
      <Icon className={cn("mb-2 h-4 w-4", active ? "text-blue-300" : "text-zinc-400")} />
      <p className={cn("text-sm", active ? "font-medium text-blue-100" : "text-zinc-300")}>{label}</p>
    </button>
  )
}

function MinimalStatCard({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: "blue" | "emerald" | "violet"
}) {
  const toneClasses = {
    blue: "from-blue-500/20 to-blue-500/5 text-blue-200",
    emerald: "from-emerald-500/20 to-emerald-500/5 text-emerald-200",
    violet: "from-violet-500/20 to-violet-500/5 text-violet-200",
  }
  return (
    <div className={cn("rounded-2xl border border-zinc-700/60 bg-gradient-to-br p-4", toneClasses[tone])}>
      <p className="text-3xl font-medium leading-none text-zinc-100">{value}</p>
      <p className="mt-2 text-sm text-zinc-300">{label}</p>
    </div>
  )
}

function buildDailyActivity(quizHistory: { date: string; total: number }[], deck: FlashcardInDB[]) {
  const days = 14
  const flashMap = new Map<string, number>()
  const quizMap = new Map<string, number>()
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    flashMap.set(key, 0)
    quizMap.set(key, 0)
  }

  for (const q of quizHistory) {
    if (quizMap.has(q.date)) {
      quizMap.set(q.date, (quizMap.get(q.date) ?? 0) + 1)
    }
  }
  for (const card of deck) {
    if (card.last_reviewed && flashMap.has(card.last_reviewed)) {
      flashMap.set(card.last_reviewed, (flashMap.get(card.last_reviewed) ?? 0) + 1)
    }
  }

  return Array.from(flashMap.keys()).map((date) => ({
    date,
    label: date.slice(5),
    flash: flashMap.get(date) ?? 0,
    quiz: quizMap.get(date) ?? 0,
    total: (flashMap.get(date) ?? 0) + (quizMap.get(date) ?? 0),
  }))
}

function isUploadIndeterminate(u: { done: boolean; step: string; pct: number }): boolean {
  return !u.done && (/\/\?\s*chunks$/i.test(u.step) || u.pct <= 0)
}

function getQuizQuestionKey(q: QuizQuestion): string {
  return `${q.pergunta}||${q.fonte}||${q.opcoes.join("||")}`
}

function QuizPlayer({
  questions,
  subjectId,
  loadingMore,
  savedQuestionKeys,
  onToggleSaveForLater,
  onOpenInPreview,
  onFinish,
}: {
  questions: QuizQuestion[]
  subjectId: string
  loadingMore: boolean
  savedQuestionKeys: Set<string>
  onToggleSaveForLater: (question: QuizQuestion) => Promise<void>
  onOpenInPreview: (file: string, page?: number, query?: string) => void
  onFinish: (answers: Array<{ selected: string; isCorrect: boolean }>) => void
}) {
  const [idx, setIdx] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [answers, setAnswers] = useState<Array<{ selected: string; isCorrect: boolean }>>([])
  const [showRef, setShowRef] = useState(false)

  const q = questions[idx]
  const isSavedForLater = savedQuestionKeys.has(getQuizQuestionKey(q))
  const isLast = idx === questions.length - 1
  const answered = selected !== null
  const correctIdx = q.correta
  const reference = parseCardReference(q.fonte)
  const fetchUrl = reference ? `/api/files/${subjectId}/${encodeURIComponent(reference.file)}` : null

  const [sourceTexts, setSourceTexts] = useState<string[]>([])
  const [sourceTextError, setSourceTextError] = useState<string | null>(null)
  useEffect(() => {
    if (!showRef || !reference?.file || !reference?.page) {
      setSourceTexts([])
      setSourceTextError(null)
      return
    }
    setSourceTextError(null)
    api.subjects.sourceText(subjectId, reference.file, reference.page)
      .then((r) => setSourceTexts(r.texts))
      .catch(() => {
        setSourceTexts([])
        setSourceTextError("Não foi possível carregar o excerto da fonte.")
      })
  }, [showRef, reference?.file, reference?.page, subjectId])
  const progressPct = ((idx + (answered ? 1 : 0)) / questions.length) * 100
  const optionLabels = ["A", "B", "C", "D"]

  function handleSelect(optIdx: number) {
    if (answered) return
    const isCorrect = optIdx === correctIdx
    setSelected(optIdx)
    setAnswers((prev) => [...prev, { selected: q.opcoes[optIdx], isCorrect }])
  }

  function handleNext() {
    if (!answered) return
    setShowRef(false)
    if (isLast) {
      onFinish(answers)
    } else {
      setIdx((v) => v + 1)
      setSelected(null)
    }
  }

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="flex items-center gap-3 text-xs text-zinc-500">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-zinc-800">
          <div
            className="h-full rounded-full bg-blue-400 transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <span className="tabular-nums shrink-0">{idx + 1} / {questions.length}</span>
      </div>

      {/* Question text */}
      <div className="rounded-2xl border border-zinc-700/60 bg-zinc-900/55 px-6 py-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">Pergunta {idx + 1}</p>
          <button
            onClick={() => onToggleSaveForLater(q)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              isSavedForLater
                ? "border-violet-500/50 bg-violet-500/15 text-violet-300"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200",
            )}
          >
            ⭐ {isSavedForLater ? "Guardada" : "Guardar para depois"}
          </button>
        </div>
        <p className="text-xl leading-snug text-zinc-100">{q.pergunta}</p>
      </div>

      {/* Answer options */}
      <div className="space-y-2">
        {q.opcoes.map((opt, i) => {
          let cls = "border-zinc-700/60 bg-zinc-900/55 text-zinc-200 hover:border-zinc-600/60 hover:bg-zinc-800/60"
          if (answered) {
            if (i === correctIdx) cls = "border-emerald-500/50 bg-emerald-500/10 text-emerald-100"
            else if (i === selected) cls = "border-red-500/50 bg-red-500/10 text-red-200"
            else cls = "border-zinc-700/40 bg-zinc-900/30 text-zinc-500"
          }
          return (
            <button
              key={i}
              onClick={() => handleSelect(i)}
              disabled={answered}
              className={cn(
                "w-full flex items-center gap-3 rounded-2xl border px-4 py-3 text-left transition-colors disabled:cursor-default",
                cls,
              )}
            >
              <span
                className={cn(
                  "grid h-7 w-7 shrink-0 place-items-center rounded-full border text-xs font-bold",
                  answered && i === correctIdx
                    ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-300"
                    : answered && i === selected && i !== correctIdx
                      ? "border-red-500/50 bg-red-500/20 text-red-300"
                      : "border-zinc-600 bg-zinc-800 text-zinc-400",
                )}
              >
                {optionLabels[i] ?? String.fromCharCode(65 + i)}
              </span>
              <span className="text-sm">{opt}</span>
              {answered && i === correctIdx && <span className="ml-auto shrink-0 text-emerald-400">✓</span>}
              {answered && i === selected && i !== correctIdx && <span className="ml-auto shrink-0 text-red-400">✗</span>}
            </button>
          )
        })}
      </div>

      {/* Post-answer: explanation + reference + next button */}
      {answered && (
        <div className="space-y-3">
          {q.explicacao && (
            <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/40 px-5 py-4">
              <p className="text-[10px] uppercase tracking-[0.16em] text-zinc-500 mb-2">Explicação</p>
              <p className="text-sm text-zinc-300">{q.explicacao}</p>
            </div>
          )}

          {reference && (
            <div>
              <button
                onClick={() => setShowRef((v) => !v)}
                className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 px-4 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-500 hover:text-zinc-200"
              >
                📄 {showRef ? "Esconder referência" : "Ver referência"}
              </button>
            </div>
          )}

          {/* Animated PDF panel */}
          <motion.div
            animate={{ height: showRef && reference ? (sourceTexts.length > 0 ? 700 : 500) : 0, opacity: showRef && reference ? 1 : 0 }}
            initial={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            {reference && (
              <div className="space-y-2 pt-1">
                {sourceTexts.length > 0 && (
                  <div className="rounded-2xl border border-amber-500/25 bg-amber-500/5 px-4 py-3">
                    <p className="text-[10px] uppercase tracking-[0.14em] text-amber-400/70 mb-2">Excerto da fonte · Pág. {reference.page}</p>
                    <div className="space-y-2 max-h-48 overflow-auto">
                      {sourceTexts.map((t, i) => (
                        <p key={i} className="text-xs leading-relaxed text-zinc-300"
                          dangerouslySetInnerHTML={{ __html: highlightKeywords(t, q.pergunta + " " + q.opcoes.join(" ")) }}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {sourceTextError && (
                  <div className="rounded-2xl border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-xs text-amber-300">
                    {sourceTextError}
                  </div>
                )}
                <div className="flex justify-end">
                  <button
                    onClick={() => reference && onOpenInPreview(reference.file, reference.page, `${q.pergunta} ${q.opcoes.join(" ")}`)}
                    className="rounded-full border border-zinc-700 px-3 py-1 text-[11px] text-zinc-300 transition-colors hover:bg-zinc-800"
                  >
                    Abrir no Preview
                  </button>
                </div>
                {fetchUrl && reference?.page && (
                  <PdfPageViewer file={fetchUrl} page={reference.page} openUrl={fetchUrl} />
                )}
              </div>
            )}
          </motion.div>

          <div className="flex justify-end">
            <button
              onClick={handleNext}
              disabled={isLast && loadingMore}
              className={cn(
                "rounded-full px-6 py-2.5 text-sm font-semibold transition-colors",
                isLast && loadingMore
                  ? "cursor-wait bg-zinc-700 text-zinc-400"
                  : "bg-zinc-100 text-zinc-900 hover:bg-white",
              )}
            >
              {isLast && loadingMore ? "A carregar…" : isLast ? "Ver resultados →" : "Próxima →"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}


