const TOKEN_KEY = "auth_token"
const COOKIE_MAX_AGE = 30 * 24 * 60 * 60 // 30 days

export function getToken(): string | null {
  if (typeof window === "undefined") return null
  // Primary: localStorage; fallback: cookie (survives hard refreshes)
  const ls = localStorage.getItem(TOKEN_KEY)
  if (ls) return ls
  const match = document.cookie.match(new RegExp(`(?:^|; )${TOKEN_KEY}=([^;]*)`))
  const fromCookie = match ? decodeURIComponent(match[1]) : null
  if (fromCookie) {
    // Re-sync localStorage so future calls don't hit the cookie again
    localStorage.setItem(TOKEN_KEY, fromCookie)
  }
  return fromCookie
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  // Also set a cookie so Next.js middleware can read it
  document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`
}

export function getDisplayName(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem("display_name")
}

export function setDisplayName(name: string): void {
  localStorage.setItem("display_name", name)
}
