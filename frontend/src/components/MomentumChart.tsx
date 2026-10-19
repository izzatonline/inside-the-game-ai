import { fmtMinute } from "@/lib/format"
import { useEffect, useRef, useState } from "react"
import { TEAM_COLORS } from "@/lib/theme"

export type MomentumPoint = { minute: number; value: number }
export type GoalMark = { minute: number; team: string }

type Props = {
  series: MomentumPoint[]; goals: GoalMark[]; cards?: GoalMark[]; codes: string[]; names: string[]; score: [number, number]; minute: number
  max?: number; playhead?: number | null; onPick?: (minute: number) => void
}

const H = 230, PAD_L = 26, PAD_R = 10, GAP = 18, AXIS = H / 2, MAXH = H / 2 - 36

/** Per-minute pressure balance: home bars above the line, away bars below, goals marked. */
export function MomentumChart({ series, goals, cards = [], codes, names, score, minute, max = 90, playhead = null, onPick }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [W, setW] = useState(560)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(() => setW(Math.max(280, Math.round(el.clientWidth))))
    ro.observe(el); setW(Math.max(280, Math.round(el.clientWidth)))
    return () => ro.disconnect()
  }, [])
  const maxMin = Math.max(max, minute)
  const svgRef = useRef<SVGSVGElement>(null)
  const dragging = useRef(false)
  const barW = (W - PAD_L - PAD_R - GAP) / maxMin
  const xOf = (m: number) => PAD_L + (m - 1) * barW + (m > 45 ? GAP : 0)
  const byMin = new Map(series.map((p) => [p.minute, p.value]))
  const htX = PAD_L + 45 * barW + GAP / 2
  const edgeX = (p: number) => PAD_L + p * barW + (p > 45 ? GAP : 0)
  const pick = (clientX: number) => {
    const r = svgRef.current!.getBoundingClientRect(), u = (clientX - r.left) * (W / r.width) - PAD_L
    const p = u >= 45 * barW + GAP ? (u - GAP) / barW : u > 45 * barW ? 45 : u / barW
    onPick?.(Math.max(0, Math.min(maxMin, Math.round(p))))
  }
  const minutes = Array.from({ length: maxMin }, (_, i) => i + 1)
  return (
    <div className="space-y-2" ref={box}>
      <div className="flex items-center justify-center gap-3 text-sm font-semibold">
        <span style={{ color: "var(--team-0)" }}>{names[0]}</span>
        <span className="text-xl font-extrabold tabular-nums">{score[0]} - {score[1]}</span>
        <span style={{ color: "var(--team-1)" }}>{names[1]}</span>
      </div>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width={W} height={H} className={`block w-full ${onPick ? "cursor-pointer touch-none" : ""}`} role="img"
        onPointerDown={onPick ? (e) => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); pick(e.clientX) } : undefined}
        onPointerMove={onPick ? (e) => { if (dragging.current) pick(e.clientX) } : undefined}
        onPointerUp={onPick ? () => { dragging.current = false } : undefined} aria-label={`Match momentum by minute, ${names[0]} above the line and ${names[1]} below`}>
        <line x1={PAD_L} x2={W - PAD_R} y1={AXIS} y2={AXIS} className="stroke-muted-foreground" strokeOpacity={0.6} />
        <line x1={htX} x2={htX} y1={20} y2={H - 28} className="stroke-muted-foreground" strokeOpacity={0.35} />
        {minutes.map((m) => {
          const v = byMin.get(m)
          if (v === undefined) return m > minute ? <rect key={m} x={xOf(m)} y={AXIS - 0.5} width={Math.max(1, barW - 1)} height={1} className="fill-muted-foreground" opacity={0.25} /> : null
          const h = Math.max(1.5, Math.abs(v) * MAXH)
          return <rect key={m} x={xOf(m)} y={v >= 0 ? AXIS - h : AXIS} width={Math.max(1, barW - 1)} height={h} rx={1} fill={TEAM_COLORS[v >= 0 ? 0 : 1]} opacity={0.92} />
        })}
        {goals.map((g, i) => {
          const home = g.team === codes[0], x = xOf(g.minute) + barW / 2, y = home ? 16 : H - 34
          const v = byMin.get(g.minute) ?? 0, tip = home ? AXIS - Math.max(0, v) * MAXH : AXIS + Math.max(0, -v) * MAXH
          return (
            <g key={i}>
              <line x1={x} x2={x} y1={home ? y + 8 : y - 8} y2={tip} stroke="currentColor" strokeOpacity={0.5} strokeDasharray="2 2" />
              <text x={x} y={y + 5} textAnchor="middle" fontSize={15}>⚽</text>
              <text x={x} y={home ? y + 22 : y - 12} textAnchor="middle" fontSize={9} className="fill-muted-foreground">{fmtMinute(g.minute)}'</text>
            </g>
          )
        })}
        {cards.map((c, i) => {
          const home = c.team === codes[0], x = xOf(c.minute) + barW / 2, y = home ? 34 : H - 52
          return <g key={'c' + i}><line x1={x} x2={x} y1={home ? y + 6 : y - 2} y2={AXIS} stroke="currentColor" strokeOpacity={0.4} strokeDasharray="2 2" /><rect x={x - 3.5} y={y - (home ? 6 : 0)} width={7} height={10} rx={1.2} fill="#facc15" /></g>
        })}
        {playhead !== null && onPick && (
          <g pointerEvents="none">
            <line x1={edgeX(playhead)} x2={edgeX(playhead)} y1={22} y2={H - 26} style={{ stroke: "var(--minute)" }} strokeWidth={2} />
            <rect x={edgeX(playhead) - 22} y={2} width={44} height={18} rx={9} style={{ fill: "var(--minute)" }} />
            <text x={edgeX(playhead)} y={15} textAnchor="middle" fontSize={11} fontWeight={800} fill="#fff">{fmtMinute(playhead)}'</text>
          </g>
        )}
        <text x={PAD_L - 6} y={AXIS + 4} textAnchor="end" fontSize={10} className="fill-muted-foreground">0'</text>
        <text x={htX} y={H - 14} textAnchor="middle" fontSize={11} fontWeight={700} className="fill-foreground">HT</text>
        <text x={W - PAD_R} y={AXIS + 14} textAnchor="end" fontSize={11} fontWeight={700} className="fill-foreground">{minute >= 90 ? "FT" : ""}</text>
        <text x={PAD_L + (45 * barW) / 2} y={H - 4} textAnchor="middle" fontSize={11} className="fill-muted-foreground">1st half</text>
        <text x={htX + GAP / 2 + ((maxMin - 45) * barW) / 2} y={H - 4} textAnchor="middle" fontSize={11} className="fill-muted-foreground">2nd half</text>
      </svg>
      <p className="text-muted-foreground text-center text-xs">{onPick ? "Tap or drag the chart to choose a moment. " : ""}Each bar is one minute: which side had more of the pressure (shots, entries into the final third, high tackles). A higher bar means a bigger edge.</p>
    </div>
  )
}
