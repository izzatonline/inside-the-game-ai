import { useMemo, useState } from "react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { TEAM_COLORS } from "@/lib/theme"
import type { Config, PlayerStat, Stats } from "@/lib/types"

type Axis = { key: string; label: string; get: (p: PlayerStat) => number; fmt?: (v: number) => string; scale?: (v: number, max: number) => number; floor: number }
const AXES: Axis[] = [
  { key: "passes", label: "Passes", get: (p) => p.passes, floor: 15 },
  { key: "acc", label: "Pass accuracy", get: (p) => p.pass_acc, fmt: (v) => `${v}%`, scale: (v) => Math.max(0, Math.min(1, (v - 50) / 50)), floor: 100 },
  { key: "diff", label: "Pass difficulty", get: (p) => p.pass_diff, floor: 45 },
  { key: "xg", label: "Shooting (xG)", get: (p) => p.xg, fmt: (v) => v.toFixed(2), floor: 0.5 },
  { key: "runs", label: "Fast runs", get: (p) => p.sprints, floor: 3 },
  { key: "top", label: "Top speed", get: (p) => p.top_speed, fmt: (v) => `${v} km/h`, scale: (v, max) => (v <= 0 ? 0 : Math.max(0, (v - 18) / Math.max(1, max - 18))), floor: 30 },
  { key: "def", label: "Defending", get: (p) => p.tackles + p.interceptions, floor: 6 },
  { key: "press", label: "Pressing", get: (p) => p.pressures, floor: 6 },
]
const EMPTY: PlayerStat = { team: "", passes: 0, passes_ok: 0, pass_acc: 0, pass_diff: 0, shots: 0, on_target: 0, goals: 0, assists: 0, xg: 0, sprints: 0, top_speed: 0, distance_km: 0, tackles: 0, interceptions: 0, pressures: 0 }

function Radar({ players, colors }: { players: PlayerStat[]; colors: string[] }) {
  const n = AXES.length, R = 92, C = 150
  const pt = (i: number, r: number) => [C + r * Math.sin((2 * Math.PI * i) / n), C - r * Math.cos((2 * Math.PI * i) / n)]
  return (
    <svg viewBox="0 0 300 300" className="mx-auto block w-full max-w-sm" role="img" aria-label="Player radar">
      {[0.25, 0.5, 0.75, 1].map((k) => <polygon key={k} points={AXES.map((_, i) => pt(i, R * k).join(",")).join(" ")} fill="none" stroke="currentColor" strokeOpacity={0.15} />)}
      {AXES.map((a, i) => {
        const [x, y] = pt(i, R + 20), [lx, ly] = pt(i, R)
        return (
          <g key={a.key}>
            <line x1={C} y1={C} x2={lx} y2={ly} stroke="currentColor" strokeOpacity={0.15} />
            <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize={9} fontWeight={600} fill="currentColor" opacity={0.8}>{a.label}</text>
          </g>
        )
      })}
      {players.map((p, k) => (
        <g key={k}>
          <polygon points={AXES.map((_, i) => pt(i, R * Math.max(0.03, (p as unknown as { _n: number[] })._n[i])).join(",")).join(" ")}
            fill={colors[k]} fillOpacity={0.28} stroke={colors[k]} strokeWidth={2} strokeLinejoin="round" />
          {AXES.map((a, i) => { const [x, y] = pt(i, R * Math.max(0.03, (p as unknown as { _n: number[] })._n[i])); return <circle key={a.key} cx={x} cy={y} r={2.6} fill={colors[k]} /> })}
        </g>
      ))}
    </svg>
  )
}

/** Radar of event-derived player stats, scaled against everyone in this match; optionally overlaid with a second player. */
export function PlayerCompareDialog({ open, onOpenChange, cfg, stats, codes, initial }: {
  open: boolean; onOpenChange: (v: boolean) => void; cfg: Config; stats: Stats | null; codes: string[]; initial: string | null
}) {
  const all = useMemo(() => codes.flatMap((c) => [...cfg.teams[c].players, ...cfg.teams[c].staff.subs.map((s) => s.name)].map((n) => ({ name: n, team: c }))), [cfg, codes])
  const [a, setA] = useState<string | null>(null)
  const [b, setB] = useState<string>("")
  const nameA = a ?? initial ?? all[9]?.name ?? ""
  const get = (n: string): PlayerStat => ({ ...EMPTY, team: all.find((p) => p.name === n)?.team ?? "", ...(stats?.players?.[n] ?? {}) })
  const maxes = AXES.map((ax) => Math.max(ax.floor, ...Object.values(stats?.players ?? {}).map((p) => ax.get(p))))
  const chosen = [nameA, b].filter(Boolean)
  const rows = chosen.map((n) => {
    const p = get(n)
    return Object.assign(p, { _n: AXES.map((ax, i) => (ax.scale ? ax.scale(ax.get(p), maxes[i]) : ax.get(p) / maxes[i])) })
  })
  const colorOf = (n: string, k: number) => (TEAM_COLORS[codes.indexOf(get(n).team)] ?? TEAM_COLORS[0]) + (k === 1 && get(chosen[0]).team === get(n).team ? "" : "")
  const colors = chosen.map((n, k) => (k === 1 && get(chosen[0]).team === get(n).team ? "#f59e0b" : colorOf(n, k)))
  const items = (skip?: string) => [{ value: "", label: "Nobody" }, ...all.filter((p) => p.name !== skip).map((p) => ({ value: p.name, label: `${p.name} (${p.team})` }))]
  const rowsTbl: [string, (p: PlayerStat) => string][] = [
    ["Passes (completed)", (p) => `${p.passes_ok}/${p.passes}`], ["Goals · assists", (p) => `${p.goals} · ${p.assists}`], ["Shots (on target)", (p) => `${p.shots} (${p.on_target})`],
    ["xG", (p) => p.xg.toFixed(2)], ["Distance covered", (p) => `${p.distance_km.toFixed(1)} km`], ["Fast runs (27+ km/h)", (p) => String(p.sprints)],
    ["Top speed", (p) => (p.top_speed ? `${p.top_speed} km/h` : "-")],
    ["Tackles · interceptions", (p) => `${p.tackles} · ${p.interceptions}`], ["Pressures", (p) => String(p.pressures)],
  ]
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Player stats</DialogTitle>
          <DialogDescription>Built from this match's events and 1-second tracking (distance, speed, fast runs), scaled against every player so far. Pick a second player to compare.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-2">
          {[{ v: nameA, set: (v: string) => setA(v), skip: b, c: colors[0] }, { v: b, set: (v: string) => setB(v), skip: nameA, c: colors[1] ?? "#9ca3af" }].map((s, i) => (
            <div key={i} className="space-y-1">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold"><i className="size-2 rounded-full" style={{ background: s.c }} />{i ? "Compare with" : "Player"}</span>
              <Select value={s.v} onValueChange={(v) => s.set(v ?? "")} items={items(s.skip)}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>{items(s.skip).filter((x) => i === 0 ? x.value : true).map((x) => <SelectItem key={x.value} value={x.value}>{x.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          ))}
        </div>
        <Radar players={rows} colors={colors} />
        <table className="w-full text-[13px] tabular-nums">
          <thead><tr className="text-muted-foreground text-[11px]"><th className="text-left font-medium">&nbsp;</th>{chosen.map((n, k) => <th key={n} className="text-right font-bold" style={{ color: colors[k] }}>{n.split(" ").slice(-1)[0]}</th>)}</tr></thead>
          <tbody>
            {rowsTbl.map(([label, f]) => (
              <tr key={label} className="border-t"><td className="text-muted-foreground py-1">{label}</td>{rows.map((p, k) => <td key={k} className="text-right font-semibold">{f(p)}</td>)}</tr>
            ))}
          </tbody>
        </table>
        <p className="text-muted-foreground text-[11px]">All data is synthetic. Distance, fast runs and top speed are measured from the synthetic 1-second tracking.</p>
      </DialogContent>
    </Dialog>
  )
}
