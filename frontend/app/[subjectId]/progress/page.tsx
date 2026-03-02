"use client"

import { use } from "react"
import { useQuery } from "@tanstack/react-query"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from "recharts"
import { api } from "@/lib/api"
import { PageHeader } from "@/components/shared/PageHeader"

export default function ProgressPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = use(params)

  const { data: subject } = useQuery({
    queryKey: ["subjects", subjectId],
    queryFn: () => api.subjects.get(subjectId),
  })

  const { data: prog } = useQuery({
    queryKey: ["progress", subjectId],
    queryFn: () => api.progress.get(subjectId),
  })

  if (!subject || !prog) return null

  const { quiz_history, topic_stats, srs_stats, file_stats } = prog

  // Chart data
  const quizData = quiz_history.map((h) => ({
    name: `${h.date.slice(5)} · ${h.topic.slice(0, 12)}`,
    pct: h.pct,
    fill: h.pct >= 70 ? "hsl(var(--success))" : h.pct >= 40 ? "hsl(var(--warning))" : "hsl(var(--destructive))",
  })).slice(-20)

  const srsData = [
    { name: "Dominadas", value: srs_stats.mastered, fill: "hsl(var(--success))" },
    { name: "A aprender", value: srs_stats.learning, fill: "hsl(var(--primary))" },
    { name: "Para rever", value: srs_stats.due, fill: "hsl(var(--warning))" },
    { name: "Novas", value: srs_stats.new, fill: "hsl(var(--muted-foreground))" },
  ].filter((d) => d.value > 0)

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <PageHeader title="Progresso" subtitle={subject.name} />

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3 mb-8">
        {[
          { label: "Ficheiros", value: file_stats.total_files },
          { label: "Páginas", value: file_stats.total_pages.toLocaleString("pt-PT") },
          { label: "Blocos", value: file_stats.total_chunks.toLocaleString("pt-PT") },
          { label: "Quizzes", value: quiz_history.length },
        ].map(({ label, value }) => (
          <div key={label} className="p-4 rounded-card bg-card border border-border shadow-card text-center">
            <p className="text-2xl font-bold text-foreground">{value}</p>
            <p className="text-xs text-muted-foreground mt-1">{label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Quiz history chart */}
        <div className="col-span-2 p-5 rounded-card bg-card border border-border shadow-card">
          <h2 className="text-sm font-semibold text-foreground mb-4">Histórico de Quizzes</h2>
          {quizData.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Sem quizzes ainda. Faz um quiz para ver os resultados aqui.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={quizData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}%`} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Bar dataKey="pct" radius={[4, 4, 0, 0]}>
                  {quizData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* SRS donut */}
        <div className="p-5 rounded-card bg-card border border-border shadow-card">
          <h2 className="text-sm font-semibold text-foreground mb-4">Flashcards SRS</h2>
          {srs_stats.total === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">Sem cartas ainda.</p>
          ) : (
            <div className="flex items-center gap-4">
              <PieChart width={120} height={120}>
                <Pie data={srsData} cx={55} cy={55} innerRadius={35} outerRadius={55} dataKey="value" paddingAngle={2}>
                  {srsData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Pie>
              </PieChart>
              <div className="space-y-1.5">
                {srsData.map((d) => (
                  <div key={d.name} className="flex items-center gap-2 text-xs">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: d.fill }} />
                    <span className="text-muted-foreground">{d.name}:</span>
                    <span className="font-medium text-foreground">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Topic stats */}
        <div className="p-5 rounded-card bg-card border border-border shadow-card">
          <h2 className="text-sm font-semibold text-foreground mb-4">Por Tópico</h2>
          {topic_stats.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">Sem dados ainda.</p>
          ) : (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {topic_stats.map((t) => (
                <div key={t.topic} className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">{t.topic}</p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <div className="flex-1 h-1 bg-muted rounded-full">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${t.avg_pct}%`,
                            background: t.avg_pct >= 70
                              ? "hsl(var(--success))"
                              : t.avg_pct >= 40 ? "hsl(var(--warning))" : "hsl(var(--destructive))",
                          }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground shrink-0">{Math.round(t.avg_pct)}%</span>
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">{t.attempts}×</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
