import { Goal, ShieldCheck, TriangleAlert, Users } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { TEAM_COLORS } from "@/lib/theme"
import type { Recap } from "@/lib/types"

function Compare({ label, h, a, dec = 0 }: { label: string; h: number; a: number; dec?: number }) {
  const tot = h + a || 1
  return (
    <div>
      <div className="grid grid-cols-[3rem_1fr_3rem] items-baseline text-sm tabular-nums">
        <b>{dec ? h.toFixed(dec) : h}</b><span className="text-muted-foreground text-center text-xs">{label}</span><b className="text-right">{dec ? a.toFixed(dec) : a}</b>
      </div>
      <div className="mt-1 flex h-1.5 overflow-hidden rounded-full">
        <div style={{ width: `${(100 * h) / tot}%`, background: TEAM_COLORS[0] }} /><div className="flex-1" style={{ background: TEAM_COLORS[1] }} />
      </div>
    </div>
  )
}

/** Full-time summary: result first, one plain sentence, the three numbers that matter, then the goals. */
export function RecapCard({ recap, codes }: { recap: Recap; codes: string[] }) {
  const [h, a] = codes
  const sh = recap.stats[h], sa = recap.stats[a]
  const yellows = recap.cards.length, subs = recap.subs.length
  return (
    <Card className="overflow-hidden border-emerald-500/40 bg-gradient-to-br from-emerald-500/10 to-transparent">
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <Badge className="bg-emerald-500 text-black hover:bg-emerald-500">Full time</Badge>
          <span className="text-muted-foreground flex items-center gap-1 text-[11px]"><ShieldCheck className="size-3" />{recap.source === "llm" ? "AI-written" : "rules-based"} · checked</span>
        </div>
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 text-center">
          <div className="min-w-0"><div className="mx-auto mb-1 size-2.5 rounded-full" style={{ background: TEAM_COLORS[0] }} /><div className="truncate text-sm font-semibold">{sh.name}</div></div>
          <div className="text-4xl font-black tracking-tight tabular-nums">{sh.goals}<span className="text-muted-foreground px-1.5">-</span>{sa.goals}</div>
          <div className="min-w-0"><div className="mx-auto mb-1 size-2.5 rounded-full" style={{ background: TEAM_COLORS[1] }} /><div className="truncate text-sm font-semibold">{sa.name}</div></div>
        </div>
        <p className="text-sm leading-relaxed">{recap.body}</p>
        <div className="space-y-2.5">
          <Compare label="Possession %" h={sh.possession_pct} a={sa.possession_pct} />
          <Compare label="Shots" h={sh.shots} a={sa.shots} />
          <Compare label="Expected goals" h={sh.xg} a={sa.xg} dec={2} />
        </div>
        {recap.goals.length > 0 && (
          <div>
            <h4 className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.12em] uppercase"><Goal className="size-3.5" />Goals</h4>
            <ul className="space-y-1">
              {recap.goals.map((g, i) => (
                <li key={i} className="grid grid-cols-[2.2rem_0.6rem_1fr_auto] items-center gap-2 text-sm">
                  <span className="font-bold text-amber-600 tabular-nums dark:text-amber-400">{g.minute}'</span>
                  <span className="size-2 rounded-full" style={{ background: TEAM_COLORS[g.team === a ? 1 : 0] }} />
                  <span className="truncate">{g.player}</span>
                  <span className="text-muted-foreground text-xs tabular-nums">{g.score_home}-{g.score_away}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-xs">
          <span className="flex items-center gap-1"><TriangleAlert className="size-3.5 text-yellow-500" />{yellows} yellow card{yellows === 1 ? "" : "s"}</span>
          <span className="flex items-center gap-1"><Users className="size-3.5" />{subs} substitution{subs === 1 ? "" : "s"}</span>
        </div>
      </CardContent>
    </Card>
  )
}
