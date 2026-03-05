"use client"

import { useState, useEffect } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { motion } from "framer-motion"
import { Search, BookOpen, ClipboardList } from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { api, type FlashcardInDB, type ProgressData, type Subject } from "@/lib/api"
import { Input } from "@/components/ui/input"
import { getDisplayName } from "@/lib/auth"
import { cn } from "@/lib/utils"

export default function HomePage() {
  const [search, setSearch] = useState("")
  const [displayName, setDisplayName] = useState<string | null>(null)

  useEffect(() => {
    setDisplayName(getDisplayName())
  }, [])

  const { data: subjects = [] } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => api.subjects.list(),
  })

  const progressQueries = useQueries({
    queries: subjects.map((subject) => ({
      queryKey: ["progress", subject.id],
      queryFn: () => api.progress.get(subject.id),
      staleTime: 60_000,
    })),
  })

  const deckQueries = useQueries({
    queries: subjects.map((subject) => ({
      queryKey: ["flashcards", subject.id],
      queryFn: () => api.flashcards.getDeck(subject.id),
      staleTime: 60_000,
    })),
  })

  const filtered = subjects.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase()),
  )

  const today = localISODate(new Date())

  const perSubject = subjects.map((subject, index) => {
    const progress = progressQueries[index]?.data
    const deck = deckQueries[index]?.data ?? []
    const quizHistory = progress?.quiz_history ?? []
    const deckTotal = deck.length
    const cardsReviewed = deck.filter((c) => c.reps > 0).length
    const quizAttempts = quizHistory.length
    const reviewedToday = deck.filter((c) => c.last_reviewed === today).length
    const quizToday = quizHistory.filter((q) => q.date === today).length
    return {
      id: subject.id,
      name: subject.name,
      status: subject.status,
      deckTotal,
      cardsReviewed,
      quizAttempts,
      reviewedToday,
      quizToday,
    }
  })

  const chartSubjects = subjects
    .map((subject, index) => ({ ...subject, index }))
    .filter(({ index }) => {
      const deck = deckQueries[index]?.data ?? []
      const quizzes = progressQueries[index]?.data?.quiz_history ?? []
      return deck.some((c) => !!c.last_reviewed) || quizzes.length > 0
    })
    .slice(0, 8)

  const chartData = buildDailyData(chartSubjects, progressQueries, deckQueries)

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-border bg-background shrink-0">
        <h1 className="text-base font-semibold text-foreground">Início</h1>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="mb-6"
        >
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            Bom estudo{displayName ? `, ${displayName}` : ""}
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            O teu assistente de estudo pessoal.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
          {/* UC list */}
          <section className="rounded-2xl border border-zinc-700/60 bg-zinc-900/45 p-4">
            <div className="mb-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
                <Input
                  placeholder="Filtrar UCs..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="h-9 border-zinc-700 bg-zinc-900/60 pl-9 text-sm"
                />
              </div>
            </div>

            {filtered.length === 0 ? (
              <div className="py-10 text-center text-sm text-zinc-500">
                Sem UCs para mostrar.
              </div>
            ) : (
              <div className="space-y-1.5">
                {filtered.map((subject, i) => {
                  const m = perSubject.find((s) => s.id === subject.id)
                  return (
                    <motion.div
                      key={subject.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.18, delay: i * 0.03 }}
                    >
                      <Link
                        href={`/${subject.id}`}
                        className="flex items-center justify-between rounded-xl border border-zinc-700/50 bg-zinc-900/50 px-3.5 py-3 transition-colors hover:bg-zinc-800/60"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <p className="truncate text-sm font-medium text-zinc-100">
                              {subject.name}
                            </p>
                            <span
                              className={cn(
                                "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
                                subject.status === "finished"
                                  ? "bg-emerald-500/15 text-emerald-300"
                                  : "bg-blue-500/15 text-blue-300",
                              )}
                            >
                              {subject.status === "finished" ? "Concluída" : "Ativa"}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-zinc-500">
                            <span className="flex items-center gap-1">
                              <BookOpen className="h-3 w-3" />
                              {m?.cardsReviewed ?? 0}/{m?.deckTotal ?? 0} cartões
                            </span>
                            <span className="flex items-center gap-1">
                              <ClipboardList className="h-3 w-3" />
                              {m?.quizAttempts ?? 0} testes
                            </span>
                            {subject.files.length > 0 && (
                              <span className="flex items-center gap-1">
                                {subject.files.length} {subject.files.length === 1 ? "ficheiro" : "ficheiros"}
                              </span>
                            )}
                          </div>
                        </div>
                        {(m?.reviewedToday ?? 0) + (m?.quizToday ?? 0) > 0 && (
                          <span className="ml-3 shrink-0 rounded-full bg-emerald-500/15 px-2.5 py-1 text-xs font-medium text-emerald-300">
                            Hoje: {(m?.reviewedToday ?? 0) + (m?.quizToday ?? 0)}
                          </span>
                        )}
                      </Link>
                    </motion.div>
                  )
                })}
              </div>
            )}
          </section>

          {/* Activity chart */}
          <section className="rounded-2xl border border-zinc-700/60 bg-zinc-900/45 p-4">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-zinc-500">
                  Atividade diária
                </p>
                <p className="text-sm text-zinc-300">Últimos 14 dias</p>
              </div>
              <div className="flex flex-wrap justify-end gap-x-3 gap-y-1">
                {chartSubjects.map((s, i) => (
                  <span key={s.id} className="flex items-center gap-1.5 text-xs text-zinc-400">
                    <span
                      className="h-2 w-2 rounded-sm"
                      style={{ backgroundColor: UC_FLASH_COLORS[i % UC_FLASH_COLORS.length] }}
                    />
                    {s.name}
                  </span>
                ))}
              </div>
            </div>

            <div className="h-[320px]">
              {chartSubjects.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} barCategoryGap="28%">
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis
                      dataKey="label"
                      stroke="#52525b"
                      tickLine={false}
                      axisLine={false}
                      fontSize={11}
                    />
                    <YAxis
                      stroke="#52525b"
                      tickLine={false}
                      axisLine={false}
                      fontSize={11}
                      allowDecimals={false}
                    />
                    <Tooltip
                      cursor={{ fill: "rgba(113,113,122,0.1)" }}
                      content={<CustomTooltip subjects={chartSubjects} />}
                    />
                    {chartSubjects.map((subject, i) => {
                      const flashColor = UC_FLASH_COLORS[i % UC_FLASH_COLORS.length]
                      const quizColor = UC_QUIZ_COLORS[i % UC_QUIZ_COLORS.length]
                      return [
                        <Bar
                          key={subject.id + "_flash"}
                          dataKey={subject.id + "_flash"}
                          name={subject.name + " — flash"}
                          stackId="total"
                          fill={flashColor}
                          radius={[0, 0, 0, 0]}
                        />,
                        <Bar
                          key={subject.id + "_quiz"}
                          dataKey={subject.id + "_quiz"}
                          name={subject.name + " — quiz"}
                          stackId="total"
                          fill={quizColor}
                          radius={[0, 0, 0, 0]}
                        />,
                      ]
                    })}
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-zinc-500">
                  Ainda sem atividade para desenhar o gráfico.
                </div>
              )}
            </div>

            {/* Type legend */}
            <div className="mt-3 flex items-center gap-4 border-t border-zinc-800 pt-3">
              <span className="flex items-center gap-1.5 text-xs text-zinc-500">
                <span className="h-2 w-4 rounded-sm bg-blue-400/80" />
                Flashcards
              </span>
              <span className="flex items-center gap-1.5 text-xs text-zinc-500">
                <span className="h-2 w-4 rounded-sm bg-violet-400/80" />
                Quizzes
              </span>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function localISODate(date: Date): string {
  const y = date.getFullYear()
  const m = `${date.getMonth() + 1}`.padStart(2, "0")
  const d = `${date.getDate()}`.padStart(2, "0")
  return `${y}-${m}-${d}`
}

// Flash color per UC (blue/teal family)
const UC_FLASH_COLORS = [
  "#7aa2ff", "#34d399", "#f59e0b", "#f472b6",
  "#22d3ee", "#10b981", "#f97316", "#a78bfa",
]
// Quiz color per UC (violet/darker shade of same UC)
const UC_QUIZ_COLORS = [
  "#a78bfa", "#6ee7b7", "#fcd34d", "#f9a8d4",
  "#67e8f9", "#6ee7b7", "#fdba74", "#c4b5fd",
]

function buildDailyData(
  subjects: Array<Subject & { index: number }>,
  progressQueries: Array<{ data?: ProgressData }>,
  deckQueries: Array<{ data?: FlashcardInDB[] }>,
) {
  const days = 14
  const dateList = Array.from({ length: days }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (days - 1 - i))
    return localISODate(d)
  })

  return dateList.map((dateStr) => {
    const row: Record<string, string | number> = {
      date: dateStr,
      label: dateStr.slice(5),
    }
    for (const subject of subjects) {
      const quizHistory = progressQueries[subject.index]?.data?.quiz_history ?? []
      const quizCount = quizHistory.filter((q) => q.date === dateStr).length
      const deck = deckQueries[subject.index]?.data ?? []
      const flashCount = deck.filter((c) => c.last_reviewed === dateStr).length
      row[subject.id + "_flash"] = flashCount
      row[subject.id + "_quiz"] = quizCount
    }
    return row
  })
}

// ── Custom tooltip ────────────────────────────────────────────────────────────

type TooltipProps = {
  active?: boolean
  payload?: Array<{ name: string; value: number; dataKey: string }>
  label?: string
  subjects: Array<Subject & { index: number }>
}

function CustomTooltip({ active, payload, label, subjects }: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  // Group by subject
  const bySubject = subjects.map((s) => {
    const flashEntry = payload.find((p) => p.dataKey === s.id + "_flash")
    const quizEntry = payload.find((p) => p.dataKey === s.id + "_quiz")
    const flash = flashEntry?.value ?? 0
    const quiz = quizEntry?.value ?? 0
    return { name: s.name, flash, quiz, total: flash + quiz }
  }).filter((s) => s.total > 0)

  if (bySubject.length === 0) return null

  return (
    <div
      style={{
        backgroundColor: "#18181b",
        border: "1px solid #3f3f46",
        borderRadius: "0.75rem",
        padding: "10px 14px",
        fontSize: 12,
        color: "#e4e4e7",
        minWidth: 160,
      }}
    >
      <p style={{ color: "#a1a1aa", marginBottom: 6, fontSize: 11 }}>{label}</p>
      {bySubject.map((s) => (
        <div key={s.name} style={{ marginBottom: 4 }}>
          <p style={{ fontWeight: 500, marginBottom: 2 }}>{s.name}</p>
          <div style={{ display: "flex", gap: 12, color: "#a1a1aa" }}>
            {s.flash > 0 && (
              <span>
                <span style={{ color: "#7aa2ff" }}>●</span> {s.flash} flash
              </span>
            )}
            {s.quiz > 0 && (
              <span>
                <span style={{ color: "#a78bfa" }}>●</span> {s.quiz} quiz
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
