import { useState } from "react"
import { ChartNoAxesCombined } from "lucide-react"
import { MatchReport, MatchReportPlaceholder } from "@/components/MatchReport"
import { PlayerCompareDialog } from "@/components/PlayerCompare"
import { Button } from "@/components/ui/button"
import { TEAM_COLORS } from "@/lib/theme"
import type { Config, Recap, Stats, TeamStats } from "@/lib/types"

type Row = [label: string, key: keyof TeamStats, decimals?: number, lowerIsBetter?: boolean]
const GROUPS: [string, Row[]][] = [
  ["Attack", [["Expected goals (xG)", "xg", 2], ["Shots", "shots"], ["On target", "on_target"], ["Off target", "shots_off"], ["Blocked", "shots_blocked"], ["Crosses", "crosses"]]],
  ["Control", [["Possession %", "possession_pct"], ["Passes", "passes"], ["Pass accuracy %", "pass_acc_pct"]]],
  ["Set pieces", [["Corners", "corners"], ["Free kicks", "free_kicks"], ["Throw-ins", "throw_ins"], ["Goal kicks", "goal_kicks"]]],
  ["Defence & discipline", [["Tackles", "tackles"], ["Interceptions", "interceptions"], ["Saves", "saves"], ["Fouls", "fouls", 0, true], ["Yellow cards", "yellow", 0, true], ["Offsides", "offsides", 0, true]]],
]

/** Two-sided bars growing from the centre; the side with the edge is bold, the other muted. */
export function TeamStatsTable({ teams, codes }: { teams: Record<string, TeamStats>; codes: string[] }) {
  const [h, a] = codes
  return (
    <div className="space-y-5">
      {GROUPS.map(([title, rows]) => (
        <section key={title}>
          <h4 className="text-muted-foreground mb-2 text-[11px] font-semibold tracking-[0.12em] uppercase">{title}</h4>
          <div className="space-y-2.5">
            {rows.map(([label, key, dec = 0, lowerBetter]) => {
              const hv = Number(teams[h][key]), av = Number(teams[a][key]), max = Math.max(hv, av, 0.0001)
              const hLead = lowerBetter ? hv < av : hv > av, aLead = lowerBetter ? av < hv : av > hv
              const fmt = (v: number) => (dec ? v.toFixed(dec) : String(v))
              return (
                <div key={String(key)}>
                  <div className="grid grid-cols-[3rem_1fr_3rem] items-baseline gap-2 tabular-nums">
                    <span className={`text-sm ${hLead ? "font-extrabold" : "text-muted-foreground font-medium"}`}>{fmt(hv)}</span>
                    <span className="text-muted-foreground text-center text-xs">{label}</span>
                    <span className={`text-right text-sm ${aLead ? "font-extrabold" : "text-muted-foreground font-medium"}`}>{fmt(av)}</span>
                  </div>
                  <div className="mt-1 grid grid-cols-2 gap-1">
                    <div className="bg-muted flex h-1.5 justify-end overflow-hidden rounded-full"><div className="h-full rounded-full transition-all duration-500" style={{ width: `${(100 * hv) / max}%`, background: TEAM_COLORS[0], opacity: hLead || hv === av ? 1 : 0.45 }} /></div>
                    <div className="bg-muted flex h-1.5 overflow-hidden rounded-full"><div className="h-full rounded-full transition-all duration-500" style={{ width: `${(100 * av) / max}%`, background: TEAM_COLORS[1], opacity: aLead || hv === av ? 1 : 0.45 }} /></div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

export function StatsPanel({ cfg, stats, codes, recap }: { cfg: Config; stats: Stats | null; codes: string[]; recap: Recap | null }) {
  const [open, setOpen] = useState(false)
  if (!stats) return <p className="text-muted-foreground py-6 text-center text-sm">Waiting for kick-off…</p>
  return (
    <div className="space-y-5">
      {recap ? <MatchReport recap={recap} codes={codes} /> : <MatchReportPlaceholder />}
      <div className="grid grid-cols-2 text-sm font-semibold">
        <span style={{ color: "var(--team-0)" }}>{stats.teams[codes[0]].name}</span>
        <span className="text-right" style={{ color: "var(--team-1)" }}>{stats.teams[codes[1]].name}</span>
      </div>
      <TeamStatsTable teams={stats.teams} codes={codes} />
      <Button variant="outline" className="w-full" onClick={() => setOpen(true)}><ChartNoAxesCombined className="size-4" />Player stats and compare</Button>
      <PlayerCompareDialog open={open} onOpenChange={setOpen} cfg={cfg} stats={stats} codes={codes} initial={null} />
    </div>
  )
}
