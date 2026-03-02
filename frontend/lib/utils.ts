import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string): string {
  if (!iso) return ""
  return new Date(iso).toLocaleDateString("pt-PT", {
    day: "2-digit",
    month: "short",
  })
}

/** Convert {{c1::term}} cloze to show blanks on front */
export function clozeToBlank(text: string): string {
  return text.replace(/\{\{c\d+::([^}]+)\}\}/g, "_______")
}

/** Highlight {{c1::term}} in cloze answers on back */
export function clozeHighlight(text: string): string {
  return text.replace(
    /\{\{c\d+::([^}]+)\}\}/g,
    '<span class="text-primary font-semibold">$1</span>'
  )
}
