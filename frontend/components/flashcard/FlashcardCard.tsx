"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Star, StarOff } from "lucide-react"
import { cn, clozeToBlank, clozeHighlight } from "@/lib/utils"
import type { FlashcardInDB } from "@/lib/api"

interface FlashcardCardProps {
  card: FlashcardInDB
  onResult: (result: "again" | "hard" | "good" | "easy") => void
  onToggleFavorite: () => void
  current: number
  total: number
}

const BUTTONS = [
  { key: "again" as const, label: "🔁 Outra vez", className: "border border-destructive text-destructive hover:bg-destructive/10" },
  { key: "hard"  as const, label: "😓 Difícil",   className: "border border-border text-muted-foreground hover:bg-muted" },
  { key: "good"  as const, label: "👍 Bom",        className: "bg-primary text-primary-foreground hover:bg-primary/90" },
  { key: "easy"  as const, label: "✅ Fácil",       className: "border border-success text-success hover:bg-success/10" },
]

export function FlashcardCard({
  card, onResult, onToggleFavorite, current, total,
}: FlashcardCardProps) {
  const [flipped, setFlipped] = useState(false)

  function handleResult(result: "again" | "hard" | "good" | "easy") {
    setFlipped(false)
    // Small delay so user sees card reset before next card
    setTimeout(() => onResult(result), 200)
  }

  return (
    <div className="flex flex-col items-center w-full max-w-2xl mx-auto">
      {/* Progress */}
      <div className="w-full flex items-center gap-3 mb-5">
        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-300"
            style={{ width: `${(current / total) * 100}%` }}
          />
        </div>
        <span className="text-xs text-muted-foreground shrink-0">{current}/{total}</span>
      </div>

      {/* Card flip container */}
      <div
        className="w-full cursor-pointer select-none"
        style={{ perspective: "1200px" }}
        onClick={() => setFlipped(!flipped)}
      >
        <motion.div
          className="relative w-full"
          style={{ transformStyle: "preserve-3d" }}
          animate={{ rotateY: flipped ? 180 : 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          {/* Front */}
          <div
            className={cn(
              "backface-hidden",
              "min-h-56 p-8 rounded-card border border-border bg-card shadow-card",
              "flex flex-col items-center justify-center text-center",
            )}
          >
            <div className="absolute top-4 right-4">
              <FavoriteButton active={card.favorite} onClick={(e) => { e.stopPropagation(); onToggleFavorite() }} />
            </div>
            <p className="text-lg font-medium text-foreground leading-relaxed">
              {clozeToBlank(card.frente)}
            </p>
            <p className="text-xs text-muted-foreground mt-6">Clica para revelar</p>
          </div>

          {/* Back */}
          <div
            className={cn(
              "backface-hidden absolute inset-0",
              "min-h-56 p-8 rounded-card border border-primary/40 bg-card shadow-card",
              "flex flex-col items-center justify-center text-center",
            )}
            style={{ transform: "rotateY(180deg)" }}
          >
            <div className="absolute top-4 right-4">
              <FavoriteButton active={card.favorite} onClick={(e) => { e.stopPropagation(); onToggleFavorite() }} />
            </div>
            <p
              className="text-lg font-medium text-foreground leading-relaxed"
              dangerouslySetInnerHTML={{ __html: clozeHighlight(card.verso) }}
            />
            {card.fonte && (
              <p className="text-xs text-muted-foreground mt-4 border-t border-border pt-3 w-full text-center">
                {card.fonte}
              </p>
            )}
          </div>
        </motion.div>
      </div>

      {/* SM-2 rating buttons — only show when flipped */}
      <motion.div
        initial={false}
        animate={{ opacity: flipped ? 1 : 0, y: flipped ? 0 : 8 }}
        transition={{ duration: 0.15 }}
        className="flex gap-3 mt-6 w-full"
        style={{ pointerEvents: flipped ? "auto" : "none" }}
      >
        {BUTTONS.map((btn) => (
          <button
            key={btn.key}
            onClick={() => handleResult(btn.key)}
            className={cn(
              "flex-1 py-2.5 rounded-btn text-sm font-medium transition-all",
              btn.className,
            )}
          >
            {btn.label}
          </button>
        ))}
      </motion.div>

      {/* Flip hint */}
      {!flipped && (
        <p className="text-xs text-muted-foreground mt-4">
          Barra de espaços ou clica para revelar
        </p>
      )}
    </div>
  )
}

function FavoriteButton({ active, onClick }: { active: boolean; onClick: React.MouseEventHandler }) {
  return (
    <button
      onClick={onClick}
      className="p-1.5 rounded-full hover:bg-muted transition-colors"
      aria-label={active ? "Remover dos favoritos" : "Adicionar aos favoritos"}
    >
      {active
        ? <Star className="w-4 h-4 fill-warning text-warning" />
        : <StarOff className="w-4 h-4 text-muted-foreground" />
      }
    </button>
  )
}
