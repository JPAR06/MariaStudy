"use client"

import { useState } from "react"
import { Search, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import type { FlashcardInDB } from "@/lib/api"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"

const STATUS_STYLES: Record<string, string> = {
  "nova":        "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  "a aprender":  "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  "para rever":  "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  "dominada":    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
}

interface DeckBrowserProps {
  cards: FlashcardInDB[]
  onDelete: (frente: string) => void
}

type StatusFilter = "all" | "nova" | "a aprender" | "para rever" | "dominada"

export function DeckBrowser({ cards, onDelete }: DeckBrowserProps) {
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")

  const filtered = cards.filter((c) => {
    const matchSearch = search
      ? c.frente.toLowerCase().includes(search.toLowerCase()) ||
        c.verso.toLowerCase().includes(search.toLowerCase())
      : true
    const matchStatus = statusFilter === "all" || c.status === statusFilter
    return matchSearch && matchStatus
  })

  // Stats
  const stats = {
    nova: cards.filter((c) => c.status === "nova").length,
    "a aprender": cards.filter((c) => c.status === "a aprender").length,
    "para rever": cards.filter((c) => c.status === "para rever").length,
    dominada: cards.filter((c) => c.status === "dominada").length,
  }

  return (
    <div>
      {/* Stats row */}
      <div className="flex gap-3 mb-5 flex-wrap">
        {(["all", "nova", "a aprender", "para rever", "dominada"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={cn(
              "px-3 py-1.5 rounded-full text-xs font-medium transition-all border",
              statusFilter === s
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border text-muted-foreground hover:bg-muted",
            )}
          >
            {s === "all" ? `Todas (${cards.length})` : `${s} (${stats[s as keyof typeof stats]})`}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder="Pesquisar cartas…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Card list */}
      <div className="flex flex-col gap-2">
        {filtered.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            Sem cartas encontradas.
          </p>
        )}
        {filtered.map((card) => (
          <DeckCard key={card.frente} card={card} onDelete={() => onDelete(card.frente)} />
        ))}
      </div>
    </div>
  )
}

function DeckCard({ card, onDelete }: { card: FlashcardInDB; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="p-4 rounded-card bg-card border border-border shadow-card">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <button
            className="w-full text-left"
            onClick={() => setExpanded(!expanded)}
          >
            <p className="text-sm font-medium text-foreground line-clamp-2">{card.frente}</p>
          </button>
          {expanded && (
            <p className="text-sm text-muted-foreground mt-2 pt-2 border-t border-border">
              {card.verso}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", STATUS_STYLES[card.status] || "")}>
            {card.status}
          </span>
          {card.card_type === "cloze" && (
            <Badge variant="outline" className="text-xs">cloze</Badge>
          )}
          <button
            onClick={onDelete}
            className="p-1.5 rounded-[6px] hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
        <span>Intervalo: {card.interval}d</span>
        <span>Repetições: {card.reps}</span>
        <span>Próxima: {card.next_review}</span>
      </div>
    </div>
  )
}
