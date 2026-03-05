import { cn } from "@/lib/utils"

interface TopicChipProps {
  label: string
  onClick?: () => void
  active?: boolean
  className?: string
}

export function TopicChip({ label, onClick, active, className }: TopicChipProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center px-3.5 py-1.5 rounded-full text-[11px] font-medium transition-colors",
        active
          ? "bg-zinc-100 text-zinc-900 dark:bg-zinc-100 dark:text-zinc-900"
          : "bg-zinc-200/80 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-700/70 dark:text-zinc-200 dark:hover:bg-zinc-600/70",
        !onClick && "cursor-default",
        className,
      )}
    >
      {label}
    </button>
  )
}
