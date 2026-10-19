import { useState } from "react"
import { Slider } from "@/components/ui/slider"
import { fmtMinute } from "@/lib/format"

type Props = { open: boolean; value: number; max: number; onCommit: (minute: number) => void; onDragging: (d: boolean) => void }

const num = (v: number | readonly number[]) => (Array.isArray(v) ? v[0] : (v as number))

/** Floating slider under the scoreboard: drag to any minute, release to jump there. */
export function TimeScrubber({ open, value, max, onCommit, onDragging }: Props) {
  const [drag, setDrag] = useState<number | null>(null)
  const shown = drag ?? value
  return (
    <div
      role="group" aria-label="Jump to a minute" aria-hidden={!open}
      className={`bg-background/95 absolute inset-x-0 top-full z-40 mt-1 rounded-xl border p-3 shadow-xl backdrop-blur transition-all duration-200 ${open ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-1 opacity-0"}`}
    >
      <div className="mb-2.5 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Jump to a moment in the match</span>
        <b className="text-(--minute) text-sm tabular-nums">{fmtMinute(Math.round(shown))}'</b>
      </div>
      <Slider
        min={0} max={max} step={1} value={[shown]}
        onValueChange={(v) => { onDragging(true); setDrag(num(v)) }}
        onValueCommitted={(v) => { setDrag(null); onDragging(false); onCommit(num(v)) }}
      />
      <div className="text-muted-foreground relative mt-2 h-4 text-[10px] tabular-nums">
        <span className="absolute left-0">0'</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${(45 / max) * 100}%` }}>HT</span>
        <span className="absolute right-0">{fmtMinute(max)}'</span>
      </div>
    </div>
  )
}
