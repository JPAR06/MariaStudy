"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { setToken, setDisplayName } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.auth.login(username.trim(), password)
      setToken(res.token)
      setDisplayName(res.display_name)
      router.replace("/")
    } catch {
      setError("Utilizador ou senha incorretos.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-4">
      <div className="w-full max-w-sm space-y-8">
        {/* Logo */}
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500/90 shadow-lg shadow-blue-500/25">
            <span className="text-xl font-semibold text-white">M</span>
          </div>
          <h1 className="text-2xl font-medium tracking-tight text-zinc-100">MariaStudy</h1>
          <p className="mt-1 text-sm text-zinc-500">Entra na tua conta para continuar</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            placeholder="Utilizador"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
            className="h-11 bg-zinc-900 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 focus:border-blue-500"
          />
          <Input
            type="password"
            placeholder="Senha"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="h-11 bg-zinc-900 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 focus:border-blue-500"
          />

          {error && (
            <p className="rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-2.5 text-sm text-red-400">
              {error}
            </p>
          )}

          <Button
            type="submit"
            disabled={loading || !username.trim() || !password.trim()}
            className="h-11 w-full rounded-xl bg-blue-500 text-white hover:bg-blue-400 disabled:opacity-50"
          >
            {loading ? "A entrar..." : "Entrar"}
          </Button>
        </form>
      </div>
    </div>
  )
}
