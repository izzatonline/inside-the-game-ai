import { Progress } from "@/components/ui/progress"
import { TEAM_COLORS } from "@/lib/theme"
import type { Stats } from "@/lib/types"

const ROWS: [string, keyof Stats["teams"][string]][] = [
  ["Possession %", "possession_pct"], ["Shots", "shots"], ["On target", "on_target"], ["xG", "xg"], ["Pass accuracy %", "pass_acc_pct"],
]

export function StatsPanel({ stats, codes }: { stats: Stats | null; codes: string[] }) {
  if (!stats) return <p className="text-muted-foreground py-6 text-center text-sm">Waiting for kick-off…</p>
  const [h, a] = codes
  return (
    <div className="space-y-4">
      {ROWS.map(([label, key]) => {
        const hv = stats.teams[h][key] as number, av = stats.teams[a][key] as number, tot = hv + av || 1
        return (
          <div key={key}>
            <div className="text-muted-foreground mb-1 text-center text-xs">{label}</div>
            <div className="grid grid-cols-[44px_1fr_44px] items-center gap-2 tabular-nums">
              <b style={{ color: TEAM_COLORS[0] }}>{hv}</b>
              <Progress value={(100 * hv) / tot} className="gap-0 [&_[data-slot=progress-track]]:bg-rose-500" style={{ ["--primary" as string]: TEAM_COLORS[0] }} />
              <b className="text-right" style={{ color: TEAM_COLORS[1] }}>{av}</b>
            </div>
          </div>
        )
      })}
    </div>
  )
}
