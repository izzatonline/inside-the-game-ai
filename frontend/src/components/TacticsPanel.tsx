import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { BADGE_COLORS, TEAM_COLORS } from "@/lib/theme"
import type { Selected, TacticsMap } from "@/lib/types"

function Meter({ label, value, max, text, color, hint }: { label: string; value: number; max: number; text: string; color: string; hint?: string }) {
  return (
    <div className="grid grid-cols-[96px_1fr_64px] items-center gap-2 text-xs">
      {hint ? (
        <Tooltip><TooltipTrigger className="text-muted-foreground cursor-help text-left underline decoration-dotted">{label}</TooltipTrigger><TooltipContent>{hint}</TooltipContent></Tooltip>
      ) : <span className="text-muted-foreground">{label}</span>}
      <Progress value={Math.min(100, (100 * value) / max)} className="gap-0" style={{ ["--primary" as string]: color }} />
      <span className="text-right tabular-nums">{text}</span>
    </div>
  )
}

export function TacticsPanel({ tactics, codes, selected, onSelect }: { tactics: TacticsMap; codes: string[]; selected: Selected; onSelect: (s: Selected) => void }) {
  if (!codes.some((c) => tactics[c])) {
    return (
      <div className="space-y-3 py-2">
        <p className="text-muted-foreground text-center text-sm">The AI reads each team's shape after ~4 match minutes…</p>
        <Skeleton className="h-28 w-full" /><Skeleton className="h-28 w-full" />
      </div>
    )
  }
  return (
    <div className="space-y-3">
      {codes.map((c, i) => {
        const p = tactics[c]
        if (!p) return null
        const color = TEAM_COLORS[i]
        return (
          <Card key={c}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="size-2.5 rounded-full" style={{ background: color }} />
                {p.name}
                <span className="ml-auto text-2xl font-extrabold tabular-nums">{p.formation}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {p.summary && (
                <div>
                  <p className="text-sm">{p.summary}</p>
                  <span className="text-muted-foreground text-[11px]">{p.summary_source === "llm" ? "AI-written" : "rules"} · fact-checked</span>
                </div>
              )}
              <div className="flex flex-wrap gap-1.5">
                <Badge className="bg-amber-400 font-bold text-black hover:bg-amber-400">{p.primary}</Badge>
                {p.tags.filter((t) => t !== p.primary).map((t) => <Badge key={t} variant="secondary">{t}</Badge>)}
              </div>
              <div className="space-y-1.5">
                <Meter label="Defensive line" value={p.line_height} max={60} text={String(p.line_height)} color={color} hint="How far up the pitch the back line defends (0 = own goal, 100 = opponent goal)." />
                <Meter label="Pressing" value={Math.max(0, 12 - p.ppda)} max={12} text={`${p.ppda} PPDA`} color={color} hint="Opponent passes allowed per defensive action. Lower means a more aggressive press." />
                <Meter label="Width" value={p.width_m} max={68} text={`${p.width_m} m`} color={color} />
                <Meter label="Direct passes" value={p.long_pct} max={40} text={`${p.long_pct}%`} color={color} />
              </div>
              <Separator />
              <h4 className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">Player roles (inferred from positions)</h4>
              <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {p.roles.map((r) => {
                  const sel = selected?.team === i && selected.idx === r.idx
                  return (
                    <button key={r.idx} onClick={() => onSelect({ team: i, idx: r.idx })}
                      className={`bg-muted/50 hover:bg-muted flex min-w-0 items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm ${sel ? "ring-2 ring-amber-400" : ""}`}>
                      <span className="min-w-9 rounded-md px-1 text-center text-[11px] font-extrabold text-black" style={{ background: BADGE_COLORS[r.short] ?? "#cbd5e1" }}>{r.short}</span>
                      <span className="min-w-0"><span className="block truncate">{r.name}</span><span className="text-muted-foreground block text-[11px]">{r.role}</span></span>
                    </button>
                  )
                })}
              </div>
              {p.options.length > 0 && (
                <>
                  <Separator />
                  <h4 className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">What {p.name} can do</h4>
                  {p.options.map((o) => (
                    <div key={o.title}><b className="block text-sm">{o.title}</b><span className="text-muted-foreground text-sm">{o.detail}</span></div>
                  ))}
                </>
              )}
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
