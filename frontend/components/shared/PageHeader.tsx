import { cn } from "@/lib/utils"

interface PageHeaderProps {
  title: string
  subtitle?: string
  action?: React.ReactNode
  className?: string
}

export function PageHeader({ title, subtitle, action, className }: PageHeaderProps) {
  return (
    <div className={cn(
      "flex items-start justify-between px-10 pt-10 pb-6 bg-transparent shrink-0",
      className,
    )}>
      <div className="min-w-0">
        <h1 className="text-2xl md:text-[1.75rem] font-medium text-foreground leading-tight tracking-tight">{title}</h1>
        {subtitle && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 truncate">{subtitle}</p>
        )}
      </div>
      {action && <div className="ml-4 shrink-0 flex items-center gap-2">{action}</div>}
    </div>
  )
}
