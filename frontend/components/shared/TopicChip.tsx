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
        "inline-flex items-center px-3 py-1 rounded-full text-xs font-medium transition-all",
        active
          ? "bg-primary text-primary-foreground shadow-sm"
          : "bg-primary/10 text-primary hover:bg-primary/20",
        !onClick && "cursor-default",
        className,
      )}
    >
      {label}
    </button>
  )
}
