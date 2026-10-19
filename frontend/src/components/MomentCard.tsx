import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { TEAM_COLORS } from "@/lib/theme"
import type { Overlay } from "@/lib/types"

export function MomentCard({ o, awayCode }: { o: Overlay; awayCode: string }) {
  const color = TEAM_COLORS[o.team === awayCode ? 1 : 0]
  return (
    <Card size="sm" className={`animate-in fade-in slide-in-from-top-2 border-l-4 ${o.kind === "goal" ? "bg-emerald-500/10" : ""}`} style={{ borderLeftColor: color }}>
      <CardContent className="space-y-1.5">
        <div className="flex items-baseline gap-2">
          <h3 className="flex-1 text-sm font-semibold">{o.headline}</h3>
          <Badge variant="secondary" className="tabular-nums text-amber-400">{o.minute}'</Badge>
        </div>
        <p className="text-sm">{o.body}</p>
        {o.why && <p className="text-muted-foreground text-xs italic">{o.why}</p>}
        <div className="flex flex-wrap items-center gap-1.5">
          {o.chips.map((c) => <Badge key={c.label} variant="outline">{c.label} {c.value}</Badge>)}
          <span className="text-muted-foreground text-[11px]">{o.source === "llm" ? "AI-written" : "rules"} · fact-checked</span>
        </div>
      </CardContent>
    </Card>
  )
}
