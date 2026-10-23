import { useState } from "react"
import { fmtMinute } from "@/lib/format"
import { ProvenanceDialog } from "@/components/ProvenanceDialog"
import { ArrowLeftRight, Goal, LayoutGrid, Medal, Send, Info, Target, Timer, TrendingUp, TriangleAlert, UserRound, Users, Wind, Zap, type LucideIcon } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { TEAM_COLORS } from "@/lib/theme"
import type { Overlay } from "@/lib/types"

const KIND: Record<string, { label: string; Icon: LucideIcon }> = {
  goal: { label: "Goal", Icon: Goal }, big_chance: { label: "Big chance", Icon: Target }, momentum_swing: { label: "Momentum", Icon: TrendingUp },
  chaos_spell: { label: "Chaos", Icon: Zap }, sprint: { label: "Sprint", Icon: Wind }, difficult_pass: { label: "Pass quality", Icon: Send },
  milestone: { label: "Milestone", Icon: Medal }, tactic_report: { label: "Shape", Icon: LayoutGrid }, tactic_shift: { label: "Tactical shift", Icon: ArrowLeftRight },
  role_reveal: { label: "Role", Icon: UserRound }, card: { label: "Card", Icon: TriangleAlert }, substitution: { label: "Substitution", Icon: Users },
  restart_late_throw_in: { label: "Restart Watch", Icon: Timer }, restart_late_goal_kick: { label: "Restart Watch", Icon: Timer },
  restart_late_keeper_hold: { label: "Restart Watch", Icon: Timer },
}

/** Placeholder with the same shape as a moment card, shown until the first moment arrives. */
export function MomentSkeleton({ fade = 1, lines = 2 }: { fade?: number; lines?: number }) {
  return (
    <li aria-hidden className="relative grid grid-cols-[34px_28px_minmax(0,1fr)] gap-x-2.5 pb-5" style={{ opacity: fade }}>
      <Skeleton className="mt-1.5 ml-auto h-3 w-6" />
      <Skeleton className="relative z-[1] mt-0.5 size-7 rounded-full" />
      <div className="space-y-2 pt-1">
        <Skeleton className="h-2.5 w-16" />
        <Skeleton className="h-4 w-3/5" />
        {Array.from({ length: lines }, (_, i) => <Skeleton key={i} className={`h-3 ${i === lines - 1 ? "w-4/5" : "w-full"}`} />)}
        <Skeleton className="ml-auto h-4 w-24 rounded-full" />
      </div>
    </li>
  )
}

/** One entry on the match timeline: minute on the rail, icon node, then the story. Goals get a hero treatment. */
export function MomentCard({ o, awayCode }: { o: Overlay; awayCode: string }) {
  const color = TEAM_COLORS[o.team === awayCode ? 1 : 0]
  const { label, Icon } = KIND[o.kind] ?? { label: o.kind, Icon: Target }
  const goal = o.kind === "goal"
  const [how, setHow] = useState(false)
  return (
    <li className="animate-in fade-in slide-in-from-top-2 relative grid grid-cols-[34px_28px_minmax(0,1fr)] gap-x-2.5 pb-5">
      <span className="pt-1 text-right text-xs font-bold text-(--minute) tabular-nums">{fmtMinute(o.minute)}'</span>
      <span className="bg-background relative z-[1] mt-0.5 grid size-7 place-items-center rounded-full border-2" style={{ borderColor: color, boxShadow: goal ? `0 0 14px ${color}88` : undefined }}>
        <Icon className="size-3.5" style={{ color }} />
      </span>
      <div className={goal ? "rounded-2xl border p-3" : "pt-0.5"} style={goal ? { borderColor: color + "66", background: `linear-gradient(135deg, ${color}26, transparent 70%)` } : undefined}>
        <div className="text-muted-foreground flex items-center gap-1.5 text-[10px] font-semibold tracking-[0.12em] uppercase">
          <span style={{ color: `var(--team-${o.team === awayCode ? 1 : 0})` }}>{label}</span>
        </div>
        <h3 className={goal ? "text-lg leading-tight font-extrabold" : "text-[15px] leading-snug font-semibold"}>{o.headline}</h3>
        <p className="text-foreground/90 mt-0.5 text-sm">{o.body.replace(/^\d+'\s*-\s*/, "")}</p>
        {o.why && <p className="text-muted-foreground mt-1.5 border-l-2 pl-2 text-xs leading-relaxed" style={{ borderColor: color + "88" }}>{o.why}</p>}
        {(
          <div className="text-muted-foreground mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
            {o.chips.map((c) => <span key={c.label}>{c.label} <b className="text-foreground tabular-nums">{c.value}</b></span>)}
            <button type="button" onClick={() => setHow(true)} aria-label="How this was made" className="hover:bg-muted ml-auto flex items-center gap-1 rounded-full border px-2 py-0.5 transition-colors">
              <Info className="size-3" />{o.source === "llm" ? "AI · fact-checked" : "Rules wording"}
            </button>
            <ProvenanceDialog o={o} open={how} onOpenChange={setHow} />
          </div>
        )}
      </div>
    </li>
  )
}
