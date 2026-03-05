/** Typed API client — all calls go through Next.js /api rewrite → FastAPI */
import { getToken } from "@/lib/auth"

const BASE = ""  // empty = uses Next.js rewrites → /api/*

function handleAuthFailure(res: Response): never {
  if (typeof window !== "undefined" && res.status === 401) {
    localStorage.removeItem("auth_token")
    localStorage.removeItem("display_name")
    document.cookie = "auth_token=; path=/; max-age=0"
    window.location.href = "/login"
  }
  throw new Error(`Auth error: ${res.status}`)
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken()
  return token
    ? { Authorization: `Bearer ${token}`, ...extra }
    : { ...extra }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: authHeaders(),
  })
  if (res.status === 401) handleAuthFailure(res)
  if (!res.ok) throw new Error(`GET ${path}: ${res.status} ${await res.text()}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401) handleAuthFailure(res)
  if (!res.ok) throw new Error(`POST ${path}: ${res.status} ${await res.text()}`)
  return res.json()
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  })
  if (res.status === 401) handleAuthFailure(res)
  if (!res.ok && res.status !== 204) throw new Error(`DELETE ${path}: ${res.status}`)
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  })
  if (res.status === 401) handleAuthFailure(res)
  if (!res.ok) throw new Error(`PUT ${path}: ${res.status} ${await res.text()}`)
  return res.json()
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Subject {
  id: string
  name: string
  created_at: string
  files: FileRecord[]
  topics: string[]
  summary: string
  topic_summaries: Record<string, string>
  status: "active" | "finished"
}

export interface FileRecord {
  name: string
  pages: number
  type: "notes" | "exercises"
  topics: string[]
}

export interface Source {
  file: string
  page: number
}

export interface AskResponse {
  answer: string
  sources: Source[]
}

export interface FlashcardBase {
  frente: string
  verso: string
  fonte: string
  card_type: "basic" | "cloze"
}

export interface FlashcardInDB extends FlashcardBase {
  interval: number
  ease: number
  reps: number
  last_reviewed: string | null
  next_review: string
  favorite: boolean
  status: "nova" | "a aprender" | "para rever" | "dominada"
}

export interface QuizQuestion {
  pergunta: string
  opcoes: string[]
  correta: number
  explicacao: string
  fonte: string
}

export interface QuizAttempt {
  date: string
  topic: string
  score: number
  total: number
  pct: number
}

export interface TopicStat {
  topic: string
  attempts: number
  avg_pct: number
  last_date: string
}

export interface SRSStats {
  total: number
  due: number
  mastered: number
  learning: number
  new: number
  favorites: number
}

export interface ProgressData {
  quiz_history: QuizAttempt[]
  topic_stats: TopicStat[]
  srs_stats: SRSStats
  file_stats: { total_files: number; total_pages: number; total_chunks: number }
  daily_activity: Record<string, number>
}

export interface DigestResponse {
  streak: number
  due_total: number
  weak_topic: string | null
  weak_topic_subject: string | null
  question_of_day: {
    frente: string
    verso: string
    fonte: string
    card_type: string
    subject_name: string
  } | null
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  // Subjects
  subjects: {
    list: () => get<Subject[]>("/api/subjects"),
    get: (id: string) => get<Subject>(`/api/subjects/${id}`),
    create: (name: string) => post<Subject>("/api/subjects", { name }),
    delete: (id: string) => del(`/api/subjects/${id}`),
    updateTopics: (id: string, topics: string[]) => put(`/api/subjects/${id}/topics`, topics),
    updateStatus: (id: string, status: "active" | "finished") =>
      put<Subject>(`/api/subjects/${id}/status`, { status }),
    deleteTopic: (id: string, topic: string) =>
      del(`/api/subjects/${id}/topics/${encodeURIComponent(topic)}`),
    refreshSummaries: (id: string) =>
      post(`/api/subjects/${id}/refresh-summaries`, {}),
    sourceText: (id: string, file: string, page: number) =>
      get<{ texts: string[] }>(`/api/subjects/${id}/source-text?file=${encodeURIComponent(file)}&page=${page}`),
  },

  // Files
  files: {
    delete: (subjectId: string, filename: string) =>
      del(`/api/subjects/${subjectId}/files/${encodeURIComponent(filename)}`),
    setType: (subjectId: string, filename: string, file_type: string) =>
      put(`/api/subjects/${subjectId}/files/${encodeURIComponent(filename)}/type`, { file_type }),
    /** Returns the URL to embed in an iframe for the PDF viewer */
    viewerUrl: (subjectId: string, filename: string, page?: number) =>
      `/api/files/${subjectId}/${encodeURIComponent(filename)}${page ? `#page=${page}` : ""}`,
  },

  // Q&A
  qa: {
    ask: (subjectId: string, question: string, topic_filter?: string) =>
      post<AskResponse>(`/api/subjects/${subjectId}/ask`, { question, topic_filter }),
    search: (question: string, top_k = 3) =>
      post("/api/search", { question, top_k }),
  },

  // Flashcards
  flashcards: {
    getDeck: (subjectId: string) =>
      get<FlashcardInDB[]>(`/api/subjects/${subjectId}/flashcards`),
    getDue: (subjectId: string) =>
      get<FlashcardInDB[]>(`/api/subjects/${subjectId}/flashcards/due`),
    getFavorites: (subjectId: string) =>
      get<FlashcardInDB[]>(`/api/subjects/${subjectId}/flashcards/favorites`),
    saveResult: (subjectId: string, card: FlashcardInDB, result: string) =>
      post(`/api/subjects/${subjectId}/flashcards/result`, { card, result }),
    toggleFavorite: (subjectId: string, card: FlashcardInDB) =>
      post<{ favorite: boolean }>(`/api/subjects/${subjectId}/flashcards/favorite`, { card }),
    delete: (subjectId: string, frente: string) =>
      del(`/api/subjects/${subjectId}/flashcards/${encodeURIComponent(frente)}`),
    clearAll: (subjectId: string) =>
      del(`/api/subjects/${subjectId}/flashcards/all`),
    import: (subjectId: string, text: string) =>
      post<{ imported: number }>(`/api/subjects/${subjectId}/flashcards/import`, { text }),
  },

  // Quiz
  quiz: {
    saveResult: (subjectId: string, topic: string, score: number, total: number) =>
      post(`/api/subjects/${subjectId}/quiz/result`, { topic, score, total }),
    getSaved: (subjectId: string) =>
      get<QuizQuestion[]>(`/api/subjects/${subjectId}/quiz/saved`),
    toggleSaved: (subjectId: string, question: QuizQuestion) =>
      post<{ saved: boolean }>(`/api/subjects/${subjectId}/quiz/saved`, { question }),
  },

  // Progress
  progress: {
    get: (subjectId: string) => get<ProgressData>(`/api/subjects/${subjectId}/progress`),
  },

  // Daily Digest
  digest: {
    get: () => get<DigestResponse>("/api/digest"),
  },

  // Auth
  auth: {
    login: (username: string, password: string) =>
      post<{ token: string; username: string; display_name: string }>(
        "/api/auth/login",
        { username, password },
      ),
  },
}
