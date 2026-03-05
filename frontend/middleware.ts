import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split(".")
    if (parts.length < 2) return true
    const payload = JSON.parse(atob(parts[1]))
    const exp = Number(payload?.exp ?? 0)
    if (!exp) return true
    return Date.now() >= exp * 1000
  } catch {
    return true
  }
}

export function middleware(request: NextRequest) {
  const token = request.cookies.get("auth_token")?.value
  const { pathname } = request.nextUrl
  const authenticated = !!token && !isTokenExpired(token)

  if (!authenticated && pathname !== "/login") {
    const res = NextResponse.redirect(new URL("/login", request.url))
    res.cookies.set("auth_token", "", { path: "/", maxAge: 0 })
    return res
  }

  if (authenticated && pathname === "/login") {
    return NextResponse.redirect(new URL("/", request.url))
  }

  return NextResponse.next()
}

export const config = {
  // Protect app pages only; never intercept Next internals/API/static files.
  matcher: ["/((?!api|_next|favicon\\.ico|.*\\..*).*)"],
}
