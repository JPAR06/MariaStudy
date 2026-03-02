"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Flame, BookOpen, AlertTriangle, Lightbulb, RotateCcw } from "lucide-react"
import type { DigestResponse } from "@/lib/api"
import { clozeToBlank } from "@/lib/utils"
import { Button } from "@/components/ui/button"

interface DigestCardProps {
  icon: React.ElementType
  label: string
  value: React.ReactNode
  color: string
}

function DigestCard({ icon: Icon, label, value, color }: DigestCardProps) {
  return (
    <div className="flex-1 min-w-0 p-4 rounded-card bg-card border border-border shadow-card">
      <div className={`inline-flex p-2 rounded-[8px] mb-3 ${color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <p className="text-xs text-muted-foreground font-medium mb-1">{label}</p>
      <div className="text-foreground font-semibold text-sm">{value}</div>
    </div>
  )
}

export function DailyDigest({ data }: { data: DigestResponse }) {
  const [showQoD, setShowQoD] = useState(false)
  const q = data.question_of_day

  return (
    <div className="mb-10">
      {/* Metric row */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <DigestCard
          icon={Flame}
          label="Sequência"
          value={`${data.streak} ${data.streak === 1 ? "dia" : "dias"}`}
          color="bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400"
        />
        <DigestCard
          icon={BookOpen}
          label="Para rever hoje"
          value={data.due_total > 0 ? `${data.due_total} cartões` : "Em dia ✓"}
          color="bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400"
        />
        {data.weak_topic && (
          <DigestCard
            icon={AlertTriangle}
            label="Ponto fraco"
            value={
              <span className="truncate block" title={data.weak_topic}>
                {data.weak_topic}
                {data.weak_topic_subject && (
                  <span className="text-muted-foreground font-normal"> · {data.weak_topic_subject}</span>
                )}
              </span>
            }
            color="bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400"
          />
        )}
        {q && (
          <DigestCard
            icon={Lightbulb}
            label="Questão do dia"
            value={
              <button
                className="text-primary text-sm font-medium hover:underline text-left"
                onClick={() => setShowQoD(!showQoD)}
              >
                {showQoD ? "Fechar" : "Ver questão →"}
              </button>
            }
            color="bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400"
          />
        )}
      </div>

      {/* Question of day expanded */}
      <AnimatePresence>
        {showQoD && q && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <QoDCard q={q} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function QoDCard({ q }: { q: NonNullable<DigestResponse["question_of_day"]> }) {
  const [revealed, setRevealed] = useState(false)
  return (
    <div className="p-5 rounded-card bg-card border border-primary/30 shadow-card mb-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-primary uppercase tracking-wide">
          Questão do dia · {q.subject_name}
        </span>
      </div>
      <p className="text-foreground font-medium mb-4">{clozeToBlank(q.frente)}</p>

      {!revealed ? (
        <Button variant="outline" size="sm" onClick={() => setRevealed(true)}>
          <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Revelar resposta
        </Button>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-3 rounded-[10px] bg-primary/5 border border-primary/20"
        >
          <p className="text-foreground text-sm">{q.verso}</p>
          {q.fonte && (
            <p className="text-xs text-muted-foreground mt-2">{q.fonte}</p>
          )}
        </motion.div>
      )}
    </div>
  )
}
