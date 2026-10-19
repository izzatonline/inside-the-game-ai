import { fmtMinute } from "@/lib/format"
import { ArrowDown, ArrowUp } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { TEAM_COLORS } from "@/lib/theme"
import type { Config, SubLog, TacticsMap } from "@/lib/types"

type Props = { cfg: Config; codes: string[]; tactics: TacticsMap; subLog: SubLog[]; cards: { team: string; player?: string | null }[]; goals: { team: string; player?: string | null }[] }

const surname = (n: string) => n.split(" ").slice(-1)[0]

/** Starting XIs on a vertical pitch (away side up, home side down), then the benches with who came on. */
export function LineupsPanel({ cfg, codes, tactics, subLog, cards, goals }: Props) {
  const nodes = codes.flatMap((c, t) => cfg.teams[c].players.map((name, i) => {
    const [d, lat] = cfg.teams[c].slots[i]  // d: 0 own goal .. 100 opp goal, lat: 0..100 across
    const subbed = subLog.find((s) => s.team === c && s.slot === i)
    return {
      c, t, i, name, subbed,
      x: t === 0 ? (lat / 100) * 62 + 3 : 65 - (lat / 100) * 62,
      y: t === 0 ? 102 - d * 0.54 : 3 + d * 0.54,
      booked: cards.some((k) => k.team === c && (k.player === name || (subbed && k.player === subbed.player_in))),
      scored: goals.filter((g) => g.team === c && g.player === name).length,
    }
  }))
  return (
    <div className="space-y-4">
      <div className="mx-auto w-full max-w-md overflow-hidden rounded-2xl border bg-[#0b2a1b] shadow-lg">
        <svg viewBox="0 0 68 105" className="block w-full" role="img" aria-label="Starting line-ups">
          <g fill="none" stroke="rgba(255,255,255,.35)" strokeWidth={0.35}>
            <rect x={0.5} y={0.5} width={67} height={104} /><line x1={0.5} x2={67.5} y1={52.5} y2={52.5} /><circle cx={34} cy={52.5} r={9.15} />
            <rect x={13.8} y={0.5} width={40.3} height={16.5} /><rect x={24.8} y={0.5} width={18.3} height={5.5} />
            <rect x={13.8} y={88} width={40.3} height={16.5} /><rect x={24.8} y={99} width={18.3} height={5.5} />
          </g>
          {[1, 0].map((t) => (
            <g key={t}>
              <text x={t ? 3 : 3} y={t ? 52 : 52} fontSize={2.6} fontWeight={800} fill={TEAM_COLORS[t]} dy={t ? -1.2 : 3.2}>{(tactics[codes[t]]?.formation ?? "") + "  " + codes[t]}</text>
            </g>
          ))}
          {nodes.map((n) => (
            <g key={n.c + n.i}>
              <circle cx={n.x} cy={n.y} r={2.9} fill={TEAM_COLORS[n.t]} stroke={n.i === 0 ? "#fbbf24" : "#fff"} strokeWidth={0.5} opacity={n.subbed ? 0.55 : 1} />
              <text x={n.x} y={n.y + 1} textAnchor="middle" fontSize={2.7} fontWeight={800} fill="#04121c">{n.i + 1}</text>
              <text x={n.x} y={n.y + 5.6} textAnchor="middle" fontSize={2.1} fontWeight={700} fill="#fff" stroke="#06150d" strokeWidth={0.45} paintOrder="stroke">{surname(n.name)}</text>
              {n.subbed && <g><circle cx={n.x + 3} cy={n.y - 2.8} r={1.5} fill="#e11d48" /><path d={`M ${n.x + 3} ${n.y - 3.6} L ${n.x + 3} ${n.y - 2} M ${n.x + 2.3} ${n.y - 2.6} L ${n.x + 3} ${n.y - 1.9} L ${n.x + 3.7} ${n.y - 2.6}`} stroke="#fff" strokeWidth={0.3} fill="none" /></g>}
              {n.booked && <rect x={n.x - 4.3} y={n.y - 4.5} width={1.8} height={2.6} rx={0.3} fill="#facc15" />}
              {n.scored > 0 && <g><circle cx={n.x + 2.7} cy={n.y + 1.9} r={1.5} fill="#fff" stroke="#06150d" strokeWidth={0.25} /><text x={n.x + 2.7} y={n.y + 2.65} textAnchor="middle" fontSize={2.1}>⚽</text>{n.scored > 1 && <text x={n.x + 4.6} y={n.y + 2.7} fontSize={2} fontWeight={800} fill="#fff" stroke="#06150d" strokeWidth={0.35} paintOrder="stroke">{n.scored}</text>}</g>}
            </g>
          ))}
        </svg>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {codes.map((c, t) => {
          const st = cfg.teams[c].staff
          return (
            <Card key={c} size="sm">
              <CardContent className="space-y-2">
                <div className="flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ background: TEAM_COLORS[t] }} /><b className="text-sm">{cfg.teams[c].name}</b></div>
                <p className="text-muted-foreground text-xs">Head coach <b className="text-foreground">{st.coach}</b> · {st.assistants.join(", ")}</p>
                <ul className="space-y-1">
                  {st.subs.map((sb) => {
                    const on = subLog.find((s) => s.team === c && s.player_in === sb.name)
                    return (
                      <li key={sb.number} className="grid grid-cols-[1.6rem_1fr_auto] items-center gap-2 text-sm">
                        <span className="text-muted-foreground text-xs tabular-nums">{sb.number}</span>
                        <span className={on ? "font-semibold" : "text-muted-foreground"}>{sb.name} <span className="text-muted-foreground text-[11px]">{sb.pos}</span></span>
                        {on ? <Badge variant="secondary" className="gap-1 text-[11px]"><ArrowUp className="size-3 text-emerald-500" />{fmtMinute(on.minute)}' <span className="text-muted-foreground">for</span> {surname(on.player_out)}</Badge> : <span className="text-muted-foreground text-[11px]">unused</span>}
                      </li>
                    )
                  })}
                </ul>
                {subLog.some((s) => s.team === c) && <p className="text-muted-foreground flex items-center gap-1 text-[11px]"><ArrowDown className="size-3 text-rose-500" />Red arrow on the pitch marks a player who was replaced.</p>}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
