import { useState } from "react"
import { ArrowDown, ArrowUp, ChartNoAxesCombined } from "lucide-react"
import { PlayerCompareDialog } from "@/components/PlayerCompare"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { fmtMinute } from "@/lib/format"
import { TEAM_COLORS } from "@/lib/theme"
import type { Config, Stats, SubLog } from "@/lib/types"

type Props = { cfg: Config; codes: string[]; stats: Stats | null; subLog: SubLog[]; cards: { team: string; player?: string | null }[]; goals: { team: string; player?: string | null }[] }

const surname = (n: string) => n.split(" ").slice(-1)[0]

/**
 * Starting XIs on a vertical pitch (away side up, home side down). Each team is laid out by its formation lines:
 * lines are spaced evenly down the half and players evenly across the line, so names never touch the next circle.
 */
export function LineupsPanel({ cfg, codes, stats, subLog, cards, goals }: Props) {
  const [pick, setPick] = useState<{ open: boolean; name: string | null }>({ open: false, name: null })
  const nodes = codes.flatMap((c, t) => {
    const team = cfg.teams[c], lines = team.lines, outfieldLines = lines.length - 1
    return lines.flatMap((row, r) => row.map((i, k) => {
      const depth = r === 0 ? 0.08 : 0.3 + ((r - 1) * 0.56) / Math.max(1, outfieldLines - 1)  // 0 own goal .. 1 half-way line
      const across = (k + 0.5) / row.length
      const name = team.players[i], subbed = subLog.find((s) => s.team === c && s.slot === i)
      const compact = row.length >= 5, sn = surname(name)
      return {
        c, t, i, name, subbed, compact, label: compact && sn.length > 9 ? sn.slice(0, 8) + "…" : sn,
        x: t === 0 ? 5 + across * 58 : 63 - across * 58,
        y: t === 0 ? 102 - depth * 49 : 3 + depth * 49,
        booked: cards.some((q) => q.team === c && (q.player === name || (subbed && q.player === subbed.player_in))),
        scored: goals.filter((g) => g.team === c && g.player === name).length,
      }
    }))
  })
  return (
    <div className="space-y-4">
      <div className="mx-auto w-full max-w-md overflow-hidden rounded-2xl border bg-[#0b2a1b] shadow-lg">
        <svg viewBox="0 0 68 105" className="block w-full" role="img" aria-label="Starting line-ups">
          {Array.from({ length: 8 }, (_, k) => <rect key={k} x={0} y={k * 13.125} width={68} height={13.125} fill={k % 2 ? "rgba(255,255,255,.035)" : "rgba(0,0,0,.06)"} />)}
          <g fill="none" stroke="rgba(255,255,255,.35)" strokeWidth={0.35}>
            <rect x={0.5} y={0.5} width={67} height={104} /><line x1={0.5} x2={67.5} y1={52.5} y2={52.5} /><circle cx={34} cy={52.5} r={9.15} />
            <rect x={13.8} y={0.5} width={40.3} height={16.5} /><rect x={24.8} y={0.5} width={18.3} height={5.5} />
            <rect x={13.8} y={88} width={40.3} height={16.5} /><rect x={24.8} y={99} width={18.3} height={5.5} />
          </g>
          {[1, 0].map((t) => (
            <text key={t} x={2.2} y={t ? 5.2 : 103.4} fontSize={2.5} fontWeight={800} fill={TEAM_COLORS[t]} stroke="#06150d" strokeWidth={0.5} paintOrder="stroke">
              {codes[t]} · {cfg.teams[codes[t]].formation}
            </text>
          ))}
          {nodes.map((n) => (
            <g key={n.c + n.i} className="cursor-pointer" role="button" tabIndex={0} aria-label={`Stats for ${n.name}`}
              onClick={() => setPick({ open: true, name: n.name })} onKeyDown={(e) => { if (e.key === "Enter") setPick({ open: true, name: n.name }) }}>
              <circle cx={n.x} cy={n.y} r={2.9} fill={TEAM_COLORS[n.t]} stroke={n.i === 0 ? "#fbbf24" : "#fff"} strokeWidth={0.5} opacity={n.subbed ? 0.55 : 1} />
              <text x={n.x} y={n.y + 1} textAnchor="middle" fontSize={cfg.teams[n.c].numbers[n.i] > 9 ? 2.3 : 2.7} fontWeight={800} fill="#04121c">{cfg.teams[n.c].numbers[n.i]}</text>
              <text x={n.x} y={n.y + 5.6} textAnchor="middle" fontSize={n.compact ? 1.75 : 2.1} fontWeight={700} fill="#fff" stroke="#06150d" strokeWidth={0.45} paintOrder="stroke">{n.label}</text>
              {n.subbed && <g><circle cx={n.x + 2.7} cy={n.y - 2.3} r={1.3} fill="#e11d48" /><path d={`M ${n.x + 2.7} ${n.y - 3} L ${n.x + 2.7} ${n.y - 1.6} M ${n.x + 2.1} ${n.y - 2.2} L ${n.x + 2.7} ${n.y - 1.6} L ${n.x + 3.3} ${n.y - 2.2}`} stroke="#fff" strokeWidth={0.28} fill="none" /></g>}
              {n.booked && <rect x={n.x + n.label.length * (n.compact ? 0.48 : 0.58) + 0.9} y={n.y + 3.6} width={1.4} height={2} rx={0.25} fill="#facc15" stroke="#06150d" strokeWidth={0.2} />}
              {n.scored > 0 && <g><circle cx={n.x + 2.7} cy={n.y + 1.9} r={1.5} fill="#fff" stroke="#06150d" strokeWidth={0.25} /><text x={n.x + 2.7} y={n.y + 2.65} textAnchor="middle" fontSize={2.1}>⚽</text>{n.scored > 1 && <text x={n.x + 4.6} y={n.y + 2.7} fontSize={2} fontWeight={800} fill="#fff" stroke="#06150d" strokeWidth={0.35} paintOrder="stroke">{n.scored}</text>}</g>}
            </g>
          ))}
        </svg>
        <div className="text-muted-foreground flex flex-wrap items-center justify-center gap-x-4 gap-y-1 bg-background/90 px-3 py-2 text-[11px]">
          <span className="flex items-center gap-1"><i className="grid size-3 place-items-center rounded-full bg-rose-600"><ArrowDown className="size-2 text-white" /></i>replaced</span>
          <span className="flex items-center gap-1"><i className="inline-block h-3 w-2 rounded-[2px] bg-yellow-400" />booked</span>
          <span className="flex items-center gap-1">⚽ goal</span>
          <span>Tap a player for stats</span>
        </div>
      </div>
      <Button variant="outline" className="w-full" onClick={() => setPick({ open: true, name: null })}><ChartNoAxesCombined className="size-4" />Player stats and compare</Button>
      <PlayerCompareDialog open={pick.open} onOpenChange={(o) => setPick((p) => ({ ...p, open: o }))} cfg={cfg} stats={stats} codes={codes} initial={pick.name} />
      <Section title="Substitutions" empty={!subLog.length && "No changes yet"}>
        <ul className="divide-y">
          {[...subLog].sort((a, b) => a.minute - b.minute).map((s, k) => {
            const t = codes.indexOf(s.team)
            return (
              <li key={k} className="grid grid-cols-[3rem_1fr] items-center gap-2 py-2">
                <span className="text-muted-foreground flex items-center gap-1.5 text-xs font-semibold tabular-nums"><i className="h-6 w-1 rounded-full" style={{ background: TEAM_COLORS[t] }} />{fmtMinute(s.minute)}'</span>
                <div className="min-w-0 text-sm leading-tight">
                  <p className="flex items-center gap-1.5 truncate font-semibold"><ArrowUp className="size-3.5 shrink-0 text-emerald-500" /><span className="truncate">{short(s.player_in)}</span><span className="text-muted-foreground text-xs font-normal tabular-nums">#{s.number}</span></p>
                  <p className="text-muted-foreground flex items-center gap-1.5 truncate"><ArrowDown className="size-3.5 shrink-0 text-rose-500" /><span className="truncate">{short(s.player_out)}</span></p>
                </div>
              </li>
            )
          })}
        </ul>
      </Section>
      <Section title="Substitute players">
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {codes.map((c, t) => (
            <div key={c} className="min-w-0">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-bold"><i className="size-2 rounded-full" style={{ background: TEAM_COLORS[t] }} />{c}</p>
              <ul className="space-y-1.5">
                {cfg.teams[c].staff.subs.map((sb) => {
                  const on = subLog.find((s) => s.team === c && s.player_in === sb.name)
                  return (
                    <li key={sb.number} className={"flex items-center gap-2 " + (on ? "" : "opacity-60")}>
                      <span className="relative grid size-7 shrink-0 place-items-center rounded-full border-2 text-[11px] font-bold tabular-nums" style={{ borderColor: on ? TEAM_COLORS[t] : undefined }}>
                        {sb.number}
                        {on && <i className="absolute -right-1 -bottom-1 grid size-3.5 place-items-center rounded-full bg-emerald-500"><ArrowUp className="size-2.5 text-white" /></i>}
                      </span>
                      <span className="min-w-0 leading-tight">
                        <span className="block truncate text-[13px] font-semibold">{short(sb.name)}</span>
                        <span className="text-muted-foreground block truncate text-[11px]">{on ? `${fmtMinute(on.minute)}' · for ${surname(on.player_out)}` : POS[sb.pos] ?? sb.pos}</span>
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      </Section>
      <Section title="Match officials">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          {[["R", cfg.referee.name, "Referee"], ["V", cfg.referee.var, "VAR"], ...cfg.referee.assistants.map((a, k) => [`A${k + 1}`, a, `Assistant ${k + 1}`])].map(([b, n, r]) => (
            <div key={r} className="flex min-w-0 items-center gap-2">
              <span className="bg-foreground text-background grid size-7 shrink-0 place-items-center rounded-full text-[11px] font-bold">{b}</span>
              <span className="min-w-0 leading-tight"><span className="block truncate text-[13px] font-semibold">{n}</span><span className="text-muted-foreground block text-[11px]">{r}</span></span>
            </div>
          ))}
        </div>
      </Section>
      <Section title="Coaches">
        <div className="grid grid-cols-2 gap-x-4">
          {codes.map((c, t) => {
            const st = cfg.teams[c].staff
            return (
              <div key={c} className="flex min-w-0 items-start gap-2">
                <span className="grid size-7 shrink-0 place-items-center rounded-full text-[11px] font-bold text-white" style={{ background: TEAM_COLORS[t] }}>C</span>
                <span className="min-w-0 leading-tight">
                  <span className="block truncate text-[13px] font-semibold">{short(st.coach)}</span>
                  <span className="text-muted-foreground block text-[11px]">Head coach</span>
                  <span className="text-muted-foreground mt-1 block text-[11px]">{st.assistants.map(short).join(" · ")}</span>
                </span>
              </div>
            )
          })}
        </div>
      </Section>
    </div>
  )
}

const POS: Record<string, string> = { GK: "Goalkeeper", DF: "Defender", MF: "Midfielder", FW: "Forward" }
const short = (n: string) => { const p = n.split(" "); return p.length > 1 ? `${p[0][0]}. ${p.slice(1).join(" ")}` : n }

function Section({ title, empty, children }: { title: string; empty?: string | false; children: React.ReactNode }) {
  return (
    <Card size="sm">
      <CardContent className="space-y-2">
        <h3 className="text-sm font-bold">{title}</h3>
        {empty ? <p className="text-muted-foreground text-xs">{empty}</p> : children}
      </CardContent>
    </Card>
  )
}
