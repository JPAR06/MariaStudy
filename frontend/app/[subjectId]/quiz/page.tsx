"use client"

import { useState, use } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { Sparkles, RotateCcw, CheckCircle2, XCircle } from "lucide-react"
import { api, type QuizQuestion } from "@/lib/api"
import { PageHeader } from "@/components/shared/PageHeader"
import { TopicChip } from "@/components/shared/TopicChip"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export default function QuizPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = use(params)

  const [topic, setTopic] = useState("Toda a UC")
  const [n, setN] = useState(5)
  const [difficulty, setDifficulty] = useState("Médio")
  const [generating, setGenerating] = useState(false)

  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [submitted, setSubmitted] = useState(false)
  const [score, setScore] = useState(0)

  const { data: subject } = useQuery({
    queryKey: ["subjects", subjectId],
    queryFn: () => api.subjects.get(subjectId),
  })
  const topics = subject?.topics ?? []

  async function handleGenerate() {
    setGenerating(true)
    try {
      const res = await api.quiz.generate(subjectId, topic, n, difficulty)
      setQuestions(res.questoes)
      setAnswers({})
      setSubmitted(false)
      setScore(0)
    } finally {
      setGenerating(false)
    }
  }

  async function handleSubmit() {
    if (Object.keys(answers).length < questions.length) return
    const correct = questions.filter((q, i) => answers[i] === q.correta).length
    setScore(correct)
    setSubmitted(true)
    await api.quiz.saveResult(subjectId, topic, correct, questions.length)
  }

  function reset() {
    setQuestions([])
    setAnswers({})
    setSubmitted(false)
    setScore(0)
  }

  const pct = questions.length > 0 ? Math.round((score / questions.length) * 100) : 0
  const scoreColor = pct >= 70 ? "text-success" : pct >= 40 ? "text-warning" : "text-destructive"

  if (!subject) return null

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <PageHeader title="Quiz" subtitle={subject.name} />

      <AnimatePresence mode="wait">
        {questions.length === 0 ? (
          /* Config panel */
          <motion.div key="config" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div className="space-y-6">
              {/* Topic */}
              <div>
                <p className="text-sm font-medium text-foreground mb-2">Tópico</p>
                <div className="flex flex-wrap gap-2">
                  {["Toda a UC", ...topics].map((t) => (
                    <TopicChip key={t} label={t} active={topic === t} onClick={() => setTopic(t)} />
                  ))}
                </div>
              </div>
              {/* N */}
              <div>
                <p className="text-sm font-medium text-foreground mb-2">Número de questões</p>
                <div className="flex gap-2">
                  {[5, 10, 15].map((v) => (
                    <button
                      key={v}
                      onClick={() => setN(v)}
                      className={cn(
                        "w-14 py-2 rounded-btn text-sm font-medium border transition-all",
                        n === v ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:bg-muted",
                      )}
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </div>
              {/* Difficulty */}
              <div>
                <p className="text-sm font-medium text-foreground mb-2">Dificuldade</p>
                <div className="flex gap-2">
                  {["Fácil", "Médio", "Difícil"].map((d) => (
                    <button
                      key={d}
                      onClick={() => setDifficulty(d)}
                      className={cn(
                        "px-4 py-2 rounded-btn text-sm font-medium border transition-all",
                        difficulty === d ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:bg-muted",
                      )}
                    >
                      {d}
                    </button>
                  ))}
                </div>
              </div>
              <Button onClick={handleGenerate} disabled={generating} className="gap-2">
                <Sparkles className="w-4 h-4" />
                {generating ? "A gerar…" : "Gerar Quiz"}
              </Button>
            </div>
          </motion.div>
        ) : submitted ? (
          /* Results */
          <motion.div key="results" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div className="text-center mb-8 p-6 rounded-card bg-card border border-border shadow-card">
              <p className={cn("text-5xl font-bold mb-2", scoreColor)}>{pct}%</p>
              <p className="text-muted-foreground">{score}/{questions.length} corretas</p>
            </div>
            <div className="space-y-4 mb-6">
              {questions.map((q, i) => {
                const userAns = answers[i]
                const correct = userAns === q.correta
                return (
                  <div key={i} className={cn(
                    "p-4 rounded-card border shadow-card",
                    correct ? "bg-success/5 border-success/30" : "bg-destructive/5 border-destructive/30",
                  )}>
                    <div className="flex gap-2 mb-2">
                      {correct
                        ? <CheckCircle2 className="w-4 h-4 text-success shrink-0 mt-0.5" />
                        : <XCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                      }
                      <p className="text-sm font-medium text-foreground">{q.pergunta}</p>
                    </div>
                    <div className="ml-6 space-y-1">
                      {q.opcoes.map((opt, j) => (
                        <p key={j} className={cn(
                          "text-sm",
                          j === q.correta && "text-success font-medium",
                          j === userAns && j !== q.correta && "text-destructive line-through",
                          j !== q.correta && j !== userAns && "text-muted-foreground",
                        )}>
                          {opt}
                        </p>
                      ))}
                      <p className="text-xs text-muted-foreground mt-2 italic">{q.explicacao}</p>
                      {q.fonte && <p className="text-xs text-muted-foreground">{q.fonte}</p>}
                    </div>
                  </div>
                )
              })}
            </div>
            <Button variant="outline" onClick={reset} className="gap-2">
              <RotateCcw className="w-4 h-4" /> Novo Quiz
            </Button>
          </motion.div>
        ) : (
          /* Quiz form */
          <motion.div key="quiz" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <div className="space-y-6 mb-6">
              {questions.map((q, i) => (
                <div key={i} className="p-5 rounded-card bg-card border border-border shadow-card">
                  <p className="text-sm font-semibold text-foreground mb-3">{i + 1}. {q.pergunta}</p>
                  <div className="space-y-2">
                    {q.opcoes.map((opt, j) => (
                      <label
                        key={j}
                        className={cn(
                          "flex items-center gap-3 p-3 rounded-[10px] cursor-pointer transition-all border",
                          answers[i] === j
                            ? "bg-primary/10 border-primary/40 text-primary"
                            : "border-border hover:bg-muted text-foreground",
                        )}
                      >
                        <input
                          type="radio"
                          name={`q${i}`}
                          checked={answers[i] === j}
                          onChange={() => setAnswers({ ...answers, [i]: j })}
                          className="sr-only"
                        />
                        <span className="w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-all border-current">
                          {answers[i] === j && <span className="w-2.5 h-2.5 rounded-full bg-primary" />}
                        </span>
                        <span className="text-sm">{opt}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-3">
              <Button
                onClick={handleSubmit}
                disabled={Object.keys(answers).length < questions.length}
              >
                Submeter ({Object.keys(answers).length}/{questions.length})
              </Button>
              <Button variant="outline" onClick={reset}>Cancelar</Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
