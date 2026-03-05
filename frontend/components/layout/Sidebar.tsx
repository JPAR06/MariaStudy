"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { useTheme } from "next-themes"
import { Home, Sun, Moon, Plus, ChevronDown, ChevronRight, ChevronsLeft, ChevronsRight, LogOut } from "lucide-react"
import { cn } from "@/lib/utils"
import { api, type Subject } from "@/lib/api"
import { clearToken, getDisplayName } from "@/lib/auth"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { theme, setTheme } = useTheme()

  const [subjects, setSubjects] = useState<Subject[]>([])
  const [open, setOpen] = useState(true)
  const [collapsed, setCollapsed] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState("")
  const [creating, setCreating] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [displayName, setDisplayName] = useState<string | null>(null)

  useEffect(() => {
    setMounted(true)
    setDisplayName(getDisplayName())
  }, [])

  function handleLogout() {
    clearToken()
    router.replace("/login")
  }

  const activeSubjectId = pathname.split("/")[1] || null
  const validId = activeSubjectId && activeSubjectId !== "" && activeSubjectId !== "favicon.ico"
    ? activeSubjectId
    : null

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
      router.push(`/${subj.id}`)
    } finally {
      setCreating(false)
    }
  }

  return (
    <aside
      className={cn(
        "flex min-h-screen shrink-0 flex-col border-r border-zinc-800/80 bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950 transition-all duration-300",
        collapsed ? "w-20" : "w-72",
      )}
    >
      <div className={cn("flex items-center", collapsed ? "justify-center px-2 py-6" : "justify-between px-5 py-6")}>
        <Link href="/" className={cn("flex items-center", collapsed ? "justify-center" : "gap-3")}>
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-blue-400/90 shadow-sm shadow-blue-500/30">
            <span className="text-[11px] font-semibold text-white">M</span>
          </div>
          {!collapsed && <span className="text-base font-medium tracking-tight text-zinc-100">MariaStudy</span>}
        </Link>
        {!collapsed && (
          <button
            onClick={() => setCollapsed(true)}
            className="rounded-full p-1.5 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
            title="Colapsar barra"
          >
            <ChevronsLeft className="h-4 w-4" />
          </button>
        )}
      </div>

      {collapsed && (
        <div className="px-2 pb-2">
          <button
            onClick={() => setCollapsed(false)}
            className="mx-auto flex h-8 w-8 items-center justify-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
            title="Expandir barra"
          >
            <ChevronsRight className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className={cn("space-y-2", collapsed ? "px-2" : "px-4")}>
        <NavLink href="/" icon={Home} label="Inicio" active={pathname === "/"} collapsed={collapsed} />
      </div>

      <div className={cn("mt-6", collapsed ? "px-2" : "px-4")}>
        <div className={cn("mb-2 flex items-center", collapsed ? "justify-center" : "justify-between px-3")}>
          {!collapsed ? (
            <button
              onClick={() => setOpen(!open)}
              className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-[0.16em] text-zinc-500 transition-colors hover:text-zinc-300"
            >
              {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Sources
            </button>
          ) : null}

          <button
            onClick={() => setCreateOpen(true)}
            className="flex h-7 w-7 items-center justify-center rounded-full text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
            title="Nova UC"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>

        {open && (
          <div className="flex flex-col gap-1">
            {subjects.length === 0 && !collapsed && <p className="px-3 py-1 text-xs text-zinc-500">Sem UCs ainda.</p>}
            {subjects.map((s) => {
              const active = s.id === validId
              return (
                <button
                  key={s.id}
                  onClick={() => router.push(`/${s.id}`)}
                  title={s.name}
                  className={cn(
                    "transition-colors",
                    collapsed
                      ? cn(
                          "mx-auto flex h-10 w-10 items-center justify-center rounded-xl text-xs font-semibold",
                          active
                            ? "bg-zinc-200 text-zinc-900"
                            : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700",
                        )
                      : cn(
                          "w-full rounded-2xl px-3 py-2 text-left text-sm",
                          active
                            ? "bg-zinc-100 font-medium text-zinc-900 shadow-sm"
                            : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100",
                        ),
                  )}
                >
                  {collapsed ? (
                    s.name.slice(0, 1).toUpperCase()
                  ) : (
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate">{s.name}</span>
                      <span
                        className={cn(
                          "shrink-0 rounded-full px-2 py-0.5 text-[10px]",
                          s.status === "finished"
                            ? "bg-emerald-500/15 text-emerald-300"
                            : "bg-blue-500/15 text-blue-300",
                        )}
                      >
                        {s.status === "finished" ? "ok" : "on"}
                      </span>
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="flex-1" />

      <div className={cn("space-y-1 pb-5", collapsed ? "px-2" : "px-4")}>
        {mounted && (
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title={theme === "dark" ? "Modo Claro" : "Modo Escuro"}
            className={cn(
              "flex items-center rounded-2xl text-xs text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100",
              collapsed ? "mx-auto h-10 w-10 justify-center" : "w-full gap-2.5 px-3 py-2",
            )}
          >
            {theme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
            {!collapsed && (theme === "dark" ? "Modo Claro" : "Modo Escuro")}
          </button>
        )}
        <button
          onClick={handleLogout}
          title="Sair"
          className={cn(
            "flex items-center rounded-2xl text-xs text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-red-400",
            collapsed ? "mx-auto h-10 w-10 justify-center" : "w-full gap-2.5 px-3 py-2",
          )}
        >
          <LogOut className="h-3.5 w-3.5 shrink-0" />
          {!collapsed && (
            <span className="flex flex-1 items-center justify-between">
              <span>{displayName ?? "Sair"}</span>
              <span className="text-zinc-600">sair</span>
            </span>
          )}
        </button>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nova UC</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="Ex: Cardiologia, Nefrologia..."
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCreate} disabled={creating || !newName.trim()}>
              {creating ? "A criar..." : "Criar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  )
}

function NavLink({
  href,
  icon: Icon,
  label,
  active,
  collapsed,
}: {
  href: string
  icon: React.ElementType
  label: string
  active: boolean
  collapsed: boolean
}) {
  return (
    <Link
      href={href}
      title={label}
      className={cn(
        "flex items-center transition-colors",
        collapsed
          ? cn(
              "mx-auto h-10 w-10 justify-center rounded-xl",
              active
                ? "bg-zinc-200 text-zinc-900"
                : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100",
            )
          : cn(
              "gap-2.5 rounded-2xl px-3 py-2 text-sm",
              active
                ? "bg-zinc-100 font-medium text-zinc-900"
                : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100",
            ),
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && label}
    </Link>
  )
}
