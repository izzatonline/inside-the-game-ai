import { useEffect, useState } from "react"
import { ArrowUp } from "lucide-react"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { fmtMinute } from "@/lib/format"
import { BADGE_COLORS, TEAM_COLORS } from "@/lib/theme"
import type { Selected, SubLog, TacticsMap } from "@/lib/types"

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

const shortName = (full: string) => { const p = full.split(" "); return p.length > 1 ? `${p[0][0]}. ${p.slice(1).join(" ")}` : full }

export function TacticsPanel({ tactics, codes, selected, onSelect, subLog }: { tactics: TacticsMap; codes: string[]; selected: Selected; onSelect: (s: Selected) => void; subLog: SubLog[] }) {
  const [open, setOpen] = useState<string[]>([codes[0]])
  // tapping a player on the pitch opens that player's team
  useEffect(() => { if (selected) setOpen([codes[selected.team]]) }, [selected, codes])

  if (!codes.some((c) => tactics[c])) {
    return (
      <div className="space-y-3 py-2">
        <p className="text-muted-foreground text-center text-sm">The AI reads each team's shape after ~4 match minutes…</p>
        <Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" />
      </div>
    )
  }
  return (
    <Accordion value={open} onValueChange={(v) => setOpen(v as string[])} className="gap-2">
      {codes.map((c, i) => {
        const p = tactics[c]
        if (!p) return null
        const color = TEAM_COLORS[i]
        return (
          <AccordionItem key={c} value={c} className="bg-card rounded-xl border px-3 not-last:border-b">
            <AccordionTrigger className="items-center hover:no-underline">
              <span className="flex min-w-0 flex-1 items-center gap-2">
                <span className="size-2.5 shrink-0 rounded-full" style={{ background: color }} />
                <span className="truncate font-semibold">{p.name}</span>
                <Badge className="bg-amber-400 font-bold text-black hover:bg-amber-400">{p.primary}</Badge>
                <span className="ml-auto pr-2 text-lg font-extrabold tabular-nums">{p.formation}</span>
              </span>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-3 pt-1">
                {p.summary && (
                  <div>
                    <p className="text-sm">{p.summary}</p>
                    <span className="text-muted-foreground text-[11px]">{p.summary_source === "llm" ? "AI-written" : "rules"} · fact-checked</span>
                  </div>
                )}
                <div className="flex flex-wrap gap-1.5">{p.tags.filter((t) => t !== p.primary).map((t) => <Badge key={t} variant="secondary">{t}</Badge>)}</div>
                <div className="space-y-1.5">
                  <Meter label="Defensive line" value={p.line_height} max={60} text={String(p.line_height)} color={color} hint="How far up the pitch the back line defends (0 = own goal, 100 = opponent goal)." />
                  <Meter label="Pressing" value={Math.max(0, 12 - p.ppda)} max={12} text={`${p.ppda} PPDA`} color={color} hint="Opponent passes allowed per defensive action. Lower means a more aggressive press." />
                  <Meter label="Width" value={p.width_m} max={68} text={`${p.width_m} m`} color={color} />
                  <Meter label="Direct passes" value={p.long_pct} max={40} text={`${p.long_pct}%`} color={color} />
                </div>
                <Separator />
                <h4 className="text-muted-foreground text-xs font-semibold tracking-wider uppercase">Player roles (inferred from positions)</h4>
                <div className="grid grid-cols-2 gap-1">
                  {p.roles.map((r) => {
                    const sel = selected?.team === i && selected.idx === r.idx
                    const sub = subLog.find((x) => x.team === c && x.slot === r.idx && x.player_in === r.name)
                    return (
                      <button key={r.idx} title={`${r.name} · ${r.role}`} onClick={() => onSelect({ team: i, idx: r.idx })}
                        className={`bg-muted/50 hover:bg-muted flex min-w-0 items-center gap-1.5 rounded-md px-1.5 py-1 text-left ${sel ? "ring-2 ring-inset ring-amber-400" : ""}`}>
                        <span className="min-w-8 shrink-0 rounded px-1 text-center text-[10px] font-extrabold text-black" style={{ background: BADGE_COLORS[r.short] ?? "#cbd5e1" }}>{r.short}</span>
                        <span className="min-w-0 leading-tight"><span className="block truncate text-[13px]">{shortName(r.name)}</span><span className="text-muted-foreground block truncate text-[10px]">{r.role}</span></span>
                        {sub && <span className="ml-auto flex shrink-0 items-center gap-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400" title={`Substitute: came on ${fmtMinute(sub.minute)}' for ${sub.player_out}`}><ArrowUp className="size-3" />{fmtMinute(sub.minute)}'</span>}
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
              </div>
            </AccordionContent>
          </AccordionItem>
        )
      })}
    </Accordion>
  )
}
