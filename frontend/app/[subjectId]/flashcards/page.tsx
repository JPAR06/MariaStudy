"use client"

import { useState, use } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import { Sparkles, RefreshCw, Import } from "lucide-react"
import { api, type FlashcardInDB } from "@/lib/api"
import { FlashcardCard } from "@/components/flashcard/FlashcardCard"
import { DeckBrowser } from "@/components/flashcard/DeckBrowser"
import { PageHeader } from "@/components/shared/PageHeader"
import { TopicChip } from "@/components/shared/TopicChip"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Slider } from "@/components/ui/slider"
import { Textarea } from "@/components/ui/textarea"

export default function FlashcardsPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = use(params)
  // useQueryClient not needed for now

  const { data: subject } = useQuery({
    queryKey: ["subjects", subjectId],
    queryFn: () => api.subjects.get(subjectId),
  })

  const { data: deck = [], refetch: refetchDeck } = useQuery({
    queryKey: ["flashcards", subjectId],
    queryFn: () => api.flashcards.getDeck(subjectId),
  })

  // ── Study state ──
  const [studyDeck, setStudyDeck] = useState<FlashcardInDB[]>([])
  const [cardIdx, setCardIdx] = useState(0)
  const [studying, setStudying] = useState(false)

  // ── Generate panel ──
  const [topic, setTopic] = useState("Toda a UC")
  const [n, setN] = useState(10)
  const [generating, setGenerating] = useState(false)

  // ── Import ──
  const [importText, setImportText] = useState("")
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<string | null>(null)

  const topics = subject?.topics ?? []

  // SRS stats from deck
  const stats = {
    total: deck.length,
    nova: deck.filter((c) => c.status === "nova").length,
    due: deck.filter((c) => c.status === "para rever").length,
    mastered: deck.filter((c) => c.status === "dominada").length,
    learning: deck.filter((c) => c.status === "a aprender").length,
  }

  async function handleGenerate() {
    setGenerating(true)
    try {
      const res = await api.flashcards.generate(subjectId, topic, n)
      const fullCards = res.flashcards.map((c) => ({
        ...c,
        interval: 1, ease: 2.5, reps: 0,
        last_reviewed: null, next_review: new Date().toISOString().split("T")[0],
        favorite: false, status: "nova" as const,
      }))
      setStudyDeck(fullCards)
      setCardIdx(0)
      setStudying(true)
      refetchDeck()
    } finally {
      setGenerating(false)
    }
  }

  function handleReviewDue() {
    const due = deck.filter((c) => c.status === "para rever" || c.status === "nova")
    if (due.length === 0) return
    setStudyDeck(due)
    setCardIdx(0)
    setStudying(true)
  }

  async function handleResult(result: "again" | "hard" | "good" | "easy") {
    const card = studyDeck[cardIdx]
    await api.flashcards.saveResult(subjectId, card, result)
    if (cardIdx + 1 < studyDeck.length) {
      setCardIdx(cardIdx + 1)
    } else {
      setStudying(false)
      refetchDeck()
    }
  }

  async function handleToggleFavorite() {
    const card = studyDeck[cardIdx]
    const res = await api.flashcards.toggleFavorite(subjectId, card)
    setStudyDeck((prev) =>
      prev.map((c, i) => i === cardIdx ? { ...c, favorite: res.favorite } : c)
    )
  }

  async function handleDeleteCard(frente: string) {
    await api.flashcards.delete(subjectId, frente)
    refetchDeck()
  }

  async function handleImport() {
    setImporting(true)
    setImportResult(null)
    try {
      const res = await api.flashcards.import(subjectId, importText)
      setImportResult(`${res.imported} carta${res.imported !== 1 ? "s" : ""} importada${res.imported !== 1 ? "s" : ""}.`)
      setImportText("")
      refetchDeck()
    } finally {
      setImporting(false)
    }
  }

  if (!subject) return null

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <PageHeader
        title="Flashcards"
        subtitle={subject.name}
      />

      <Tabs defaultValue="study">
        <TabsList className="mb-6">
          <TabsTrigger value="study">Estudar</TabsTrigger>
          <TabsTrigger value="deck">
            Baralho {deck.length > 0 && <span className="ml-1.5 text-xs bg-muted px-1.5 py-0.5 rounded-full">{deck.length}</span>}
          </TabsTrigger>
          <TabsTrigger value="import">Importar</TabsTrigger>
        </TabsList>

        {/* ── Study tab ── */}
        <TabsContent value="study">
          <AnimatePresence mode="wait">
            {studying ? (
              <motion.div
                key="study"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                <div className="flex justify-between items-center mb-6">
                  <h2 className="font-semibold text-foreground">{topic}</h2>
                  <button
                    onClick={() => setStudying(false)}
                    className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Sair
                  </button>
                </div>
                <FlashcardCard
                  card={studyDeck[cardIdx]}
                  onResult={handleResult}
                  onToggleFavorite={handleToggleFavorite}
                  current={cardIdx + 1}
                  total={studyDeck.length}
                />
              </motion.div>
            ) : (
              <motion.div
                key="config"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                {/* Stats row */}
                <div className="grid grid-cols-4 gap-3 mb-8">
                  {[
                    { label: "Total", value: stats.total, color: "text-foreground" },
                    { label: "Novas", value: stats.nova, color: "text-primary" },
                    { label: "Para rever", value: stats.due, color: "text-orange-500" },
                    { label: "Dominadas", value: stats.mastered, color: "text-success" },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="p-4 rounded-card bg-card border border-border shadow-card text-center">
                      <p className={`text-2xl font-bold ${color}`}>{value}</p>
                      <p className="text-xs text-muted-foreground mt-1">{label}</p>
                    </div>
                  ))}
                </div>

                {/* Topic selector */}
                <div className="mb-5">
                  <p className="text-sm font-medium text-foreground mb-2">Tópico</p>
                  <div className="flex flex-wrap gap-2">
                    {["Toda a UC", ...topics].map((t) => (
                      <TopicChip
                        key={t}
                        label={t}
                        active={topic === t}
                        onClick={() => setTopic(t)}
                      />
                    ))}
                  </div>
                </div>

                {/* N slider */}
                <div className="mb-6">
                  <p className="text-sm font-medium text-foreground mb-2">
                    Número de cartas: <span className="text-primary">{n}</span>
                  </p>
                  <Slider
                    min={5} max={20} step={1} value={[n]}
                    onValueChange={([v]) => setN(v)}
                    className="max-w-xs"
                  />
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                  <Button onClick={handleGenerate} disabled={generating} className="gap-2">
                    <Sparkles className="w-4 h-4" />
                    {generating ? "A gerar…" : "Gerar Flashcards"}
                  </Button>
                  {stats.due > 0 && (
                    <Button variant="outline" onClick={handleReviewDue} className="gap-2">
                      <RefreshCw className="w-4 h-4" />
                      Rever {stats.due} pendente{stats.due !== 1 ? "s" : ""}
                    </Button>
                  )}
                </div>

                {/* Completion message */}
                {studyDeck.length > 0 && !studying && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-6 p-4 rounded-card bg-success/10 border border-success/30 text-success text-sm font-medium"
                  >
                    ✅ Sessão concluída! {studyDeck.length} carta{studyDeck.length !== 1 ? "s" : ""} estudada{studyDeck.length !== 1 ? "s" : ""}.
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </TabsContent>

        {/* ── Deck tab ── */}
        <TabsContent value="deck">
          <DeckBrowser cards={deck} onDelete={handleDeleteCard} />
        </TabsContent>

        {/* ── Import tab ── */}
        <TabsContent value="import">
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-foreground mb-1">Importar cartas</p>
              <p className="text-xs text-muted-foreground mb-3">
                Formato: <code className="bg-muted px-1 rounded">frente TAB verso</code> ou{" "}
                <code className="bg-muted px-1 rounded">frente ; verso</code> — uma carta por linha.
                Suporta formato Anki cloze <code className="bg-muted px-1 rounded">{"{{c1::termo}}"}</code>.
              </p>
              <Textarea
                placeholder="Exemplo:&#10;O que é epilepsia?	Disfunção cerebral paroxística…&#10;{{c1::Fenitoína}} é usada para tratar epilepsia	Fenitoína"
                rows={8}
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                className="font-mono text-sm"
              />
            </div>
            {importResult && (
              <p className="text-sm text-success font-medium">{importResult}</p>
            )}
            <Button
              onClick={handleImport}
              disabled={importing || !importText.trim()}
              className="gap-2"
            >
              <Import className="w-4 h-4" />
              {importing ? "A importar…" : "Importar"}
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
