"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Search } from "lucide-react"
import { api } from "@/lib/api"
import { DailyDigest } from "@/components/home/DailyDigest"
import { SubjectCard } from "@/components/home/SubjectCard"
import { Input } from "@/components/ui/input"

export default function HomePage() {
  const [search, setSearch] = useState("")

  const { data: subjects = [] } = useQuery({
    queryKey: ["subjects"],
    queryFn: () => api.subjects.list(),
  })

  const { data: digest } = useQuery({
    queryKey: ["digest"],
    queryFn: () => api.digest.get(),
    staleTime: 60_000,
  })

  const filtered = subjects.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="mb-8"
      >
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Bom estudo, Maria 👋
        </h1>
        <p className="text-muted-foreground mt-1">O teu assistente de estudo pessoal.</p>
      </motion.div>

      {digest && <DailyDigest data={digest} />}

      <div className="flex items-center gap-3 mb-5">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Filtrar UCs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          {subjects.length === 0 ? (
            <>
              <p className="text-lg font-medium mb-2">Sem UCs ainda</p>
              <p className="text-sm">Cria uma nova UC na barra lateral para começar.</p>
            </>
          ) : (
            <p className="text-sm">Nenhuma UC encontrada para &quot;{search}&quot;.</p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((subject, i) => (
            <motion.div
              key={subject.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: i * 0.04 }}
            >
              <SubjectCard subject={subject} />
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
