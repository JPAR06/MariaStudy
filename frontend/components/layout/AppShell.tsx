"use client"

import { useEffect, useState } from "react"
import { usePathname } from "next/navigation"
import { useRouter } from "next/navigation"
import { Sidebar } from "./Sidebar"
import { UploadProvider } from "@/lib/upload-context"

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const isAuthPage = pathname === "/login"
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    if (isAuthPage) {
      setChecked(true)
      return
    }
    const hasCookie = document.cookie.includes("auth_token=")
    const hasLocal = !!localStorage.getItem("auth_token")
    if (!hasCookie && !hasLocal) {
      router.replace("/login")
      return
    }
    setChecked(true)
  }, [isAuthPage, router])

  if (isAuthPage) {
    return <>{children}</>
  }
  if (!checked) return null

  return (
    <UploadProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-hidden">
          {children}
        </main>
      </div>
    </UploadProvider>
  )
}
