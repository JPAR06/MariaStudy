"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { FileText, Layers, ArrowRight } from "lucide-react"
import type { Subject } from "@/lib/api"

interface SubjectCardProps {
  subject: Subject
  chunkCount?: number
}

export function SubjectCard({ subject, chunkCount }: SubjectCardProps) {
  return (
    <motion.div
      whileHover={{ y: -2, boxShadow: "0 8px 24px rgba(0,0,0,.10)" }}
      transition={{ duration: 0.15 }}
    >
      <Link
        href={`/${subject.id}/flashcards`}
        className="block p-5 rounded-card bg-card border border-border shadow-card hover:shadow-card-hover transition-shadow"
      >
        <div className="flex items-start justify-between mb-3">
          <h3 className="font-semibold text-foreground truncate pr-2">{subject.name}</h3>
          <ArrowRight className="w-4 h-4 text-muted-foreground shrink-0" />
        </div>

        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <FileText className="w-3.5 h-3.5" />
            {subject.files.length} {subject.files.length === 1 ? "ficheiro" : "ficheiros"}
          </span>
          {chunkCount !== undefined && (
            <span className="flex items-center gap-1">
              <Layers className="w-3.5 h-3.5" />
              {chunkCount.toLocaleString("pt-PT")} blocos
            </span>
          )}
        </div>

        {subject.topics.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {subject.topics.slice(0, 3).map((t) => (
              <span
                key={t}
                className="inline-block px-2 py-0.5 rounded-full text-xs bg-primary/10 text-primary"
              >
                {t}
              </span>
            ))}
            {subject.topics.length > 3 && (
              <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-muted text-muted-foreground">
                +{subject.topics.length - 3}
              </span>
            )}
          </div>
        )}
      </Link>
    </motion.div>
  )
}
