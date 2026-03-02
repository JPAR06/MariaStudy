"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useTheme } from "next-themes"
import {
  Home, FileText, BookOpen, MessageSquare,
  CreditCard, ClipboardList, BarChart2,
  Sun, Moon, Plus, ChevronDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { api, type Subject } from "@/lib/api"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

interface NavItem {
  label: string
  href: string
  icon: React.ElementType
}

function subjectNav(id: string): NavItem[] {
  return [
    { label: "Ficheiros",  href: `/${id}/files`,      icon: FileText },
    { label: "Tópicos",    href: `/${id}/topics`,     icon: BookOpen },
    { label: "Q&A",        href: `/${id}/qa`,         icon: MessageSquare },
    { label: "Flashcards", href: `/${id}/flashcards`, icon: CreditCard },
    { label: "Quiz",       href: `/${id}/quiz`,       icon: ClipboardList },
    { label: "Progresso",  href: `/${id}/progress`,   icon: BarChart2 },
  ]
}

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { theme, setTheme } = useTheme()

  const [subjects, setSubjects] = useState<Subject[]>([])
  const [open, setOpen] = useState(false)  // subject dropdown
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState("")
  const [creating, setCreating] = useState(false)

  // Derive active subject from URL
  const activeSubjectId = pathname.startsWith("/")
    ? pathname.split("/")[1]
    : null
  const validId = activeSubjectId && activeSubjectId !== "" && activeSubjectId !== "favicon.ico"
    ? activeSubjectId : null
  const activeSubject = subjects.find((s) => s.id === validId)

  useEffect(() => {
    api.subjects.list().then(setSubjects).catch(console.error)
  }, [pathname])

  async function handleCreate() {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const subj = await api.subjects.create(newName.trim())
      setSubjects((prev) => [...prev, subj])
      setCreateOpen(false)
      setNewName("")
      router.push(`/${subj.id}/files`)
    } finally {
      setCreating(false)
    }
  }

  return (
    <aside className="flex flex-col w-64 min-h-screen border-r border-border bg-card px-3 py-4 gap-1 shrink-0">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2 px-3 py-2 mb-2">
        <span className="text-xl font-bold tracking-tight text-foreground">
          Maria<span className="text-primary">Study</span>
        </span>
      </Link>

      {/* Home link */}
      <NavLink href="/" icon={Home} label="Início" active={pathname === "/"} />

      <div className="h-px bg-border mx-2 my-2" />

      {/* Subject selector */}
      <div className="px-1">
        <button
          onClick={() => setOpen(!open)}
          className={cn(
            "w-full flex items-center justify-between px-3 py-2 rounded-[10px] text-sm font-medium transition-colors",
            "hover:bg-muted text-muted-foreground",
          )}
        >
          <span className="truncate">
            {activeSubject ? activeSubject.name : "Selecionar UC"}
          </span>
          <ChevronDown
            className={cn("w-4 h-4 shrink-0 transition-transform", open && "rotate-180")}
          />
        </button>

        {open && (
          <div className="mt-1 ml-1 flex flex-col gap-0.5">
            {subjects.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  router.push(`/${s.id}/flashcards`)
                  setOpen(false)
                }}
                className={cn(
                  "w-full text-left px-3 py-1.5 rounded-[8px] text-sm transition-colors truncate",
                  s.id === validId
                    ? "bg-primary/10 text-primary font-medium"
                    : "hover:bg-muted text-muted-foreground",
                )}
              >
                {s.name}
              </button>
            ))}
            <button
              onClick={() => { setCreateOpen(true); setOpen(false) }}
              className="w-full flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-sm text-muted-foreground hover:bg-muted transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Nova UC
            </button>
          </div>
        )}
      </div>

      {/* Subject nav links */}
      {validId && (
        <>
          <div className="h-px bg-border mx-2 my-2" />
          <div className="flex flex-col gap-0.5">
            {subjectNav(validId).map((item) => (
              <NavLink
                key={item.href}
                href={item.href}
                icon={item.icon}
                label={item.label}
                active={pathname === item.href}
              />
            ))}
          </div>
        </>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Dark mode toggle */}
      <button
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        className="flex items-center gap-2 px-3 py-2 rounded-[10px] text-sm text-muted-foreground hover:bg-muted transition-colors"
      >
        {theme === "dark"
          ? <><Sun className="w-4 h-4" /> Modo Claro</>
          : <><Moon className="w-4 h-4" /> Modo Escuro</>
        }
      </button>

      {/* Create subject dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nova UC</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="Ex: Cardiologia, Nefrologia…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancelar</Button>
            <Button onClick={handleCreate} disabled={creating || !newName.trim()}>
              {creating ? "A criar…" : "Criar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  )
}

function NavLink({
  href, icon: Icon, label, active,
}: {
  href: string
  icon: React.ElementType
  label: string
  active: boolean
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-sm font-medium transition-colors",
        active
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon className="w-4 h-4 shrink-0" />
      {label}
    </Link>
  )
}
