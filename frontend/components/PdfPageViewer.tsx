"use client"

export default function PdfPageViewer({
  file,
  page,
  openUrl,
}: {
  file: string
  page: number
  openUrl: string
}) {
  const src = `${file}#page=${page}`
  return (
    <div className="relative overflow-hidden rounded-2xl border border-zinc-700/60 bg-zinc-950" style={{ height: 440 }}>
      <iframe
        key={src}
        title="Referência PDF"
        src={src}
        className="h-full w-full"
      />
      <a
        href={openUrl}
        target="_blank"
        rel="noreferrer"
        className="absolute bottom-2 right-2 rounded-full border border-zinc-600 bg-zinc-900/80 px-2.5 py-1 text-[10px] text-zinc-400 backdrop-blur-sm hover:text-zinc-200"
      >
        ↗
      </a>
    </div>
  )
}
