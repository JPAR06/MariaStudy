"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import type { Source } from "@/lib/api"

interface ChatMessageProps {
  role: "user" | "assistant"
  content: string
  sources?: Source[]
  onCitationClick?: (source: Source) => void
}

export function ChatMessage({ role, content, sources, onCitationClick }: ChatMessageProps) {
  const [showSources, setShowSources] = useState(false)
  const isUser = role === "user"

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className={cn("flex gap-3", isUser && "flex-row-reverse")}
    >
      {/* Avatar */}
      <div className={cn(
        "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 mt-0.5",
        isUser
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-muted-foreground",
      )}>
        {isUser ? "M" : "AI"}
      </div>

      {/* Bubble */}
      <div className={cn("max-w-[78%]", isUser && "items-end flex flex-col")}>
        <div className={cn(
          "px-4 py-3 rounded-[14px] text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground rounded-tr-sm"
            : "bg-card border border-border text-foreground rounded-tl-sm",
        )}>
          {content}
        </div>

        {/* Sources */}
        {sources && sources.length > 0 && (
          <div className="mt-1.5 ml-1">
            <button
              onClick={() => setShowSources(!showSources)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showSources ? "▾" : "▸"} {sources.length} fonte{sources.length !== 1 ? "s" : ""}
            </button>
            {showSources && (
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {sources.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => onCitationClick?.(s)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                  >
                    [{i + 1}] {s.file.split("/").pop()?.slice(0, 20)}… · p.{s.page}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  )
}
