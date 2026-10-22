import { useEffect, useRef } from "react"
import { Lock } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TEAM_COLORS, teamRgb } from "@/lib/theme"
import type { Recap } from "@/lib/types"


/** Smooth territory map: blue where the home side operated more, rose where the away side did. */
function TerritoryMap({ heat }: { heat: Recap["report"]["heat"] }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const c = ref.current!, W = 210, H = 136
    c.width = W; c.height = H
    const g = c.getContext("2d")!, img = g.createImageData(W, H)
    const at = (m: number[][], x: number, y: number) => m[Math.max(0, Math.min(heat.rows - 1, y))][Math.max(0, Math.min(heat.cols - 1, x))]
    const bil = (m: number[][], gx: number, gy: number) => {
      const x0 = Math.floor(gx), y0 = Math.floor(gy), fx = gx - x0, fy = gy - y0
      return (at(m, x0, y0) * (1 - fx) + at(m, x0 + 1, y0) * fx) * (1 - fy) + (at(m, x0, y0 + 1) * (1 - fx) + at(m, x0 + 1, y0 + 1) * fx) * fy
    }
    let k = 0
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const gx = (x / W) * heat.cols - 0.5, gy = (y / H) * heat.rows - 0.5
      const v = bil(heat.v, gx, gy), w = bil(heat.w, gx, gy), col = [teamRgb(0), teamRgb(1)][v >= 0 ? 0 : 1]
      img.data[k++] = col[0]; img.data[k++] = col[1]; img.data[k++] = col[2]; img.data[k++] = Math.min(1, Math.abs(v) * 2.4) * (0.3 + 0.7 * w) * 240
    }
    g.putImageData(img, 0, 0)
  }, [heat])
  return (
    <div className="bg-muted/60 relative aspect-[105/68] w-full overflow-hidden rounded-xl border">
      <canvas ref={ref} className="absolute inset-0 h-full w-full" />
      <svg viewBox="0 0 105 68" className="text-foreground/40 absolute inset-0 h-full w-full" fill="none" stroke="currentColor" strokeWidth={0.35}>
        <rect x={0.3} y={0.3} width={104.4} height={67.4} /><line x1={52.5} x2={52.5} y1={0.3} y2={67.7} /><circle cx={52.5} cy={34} r={9.15} />
        <rect x={0.3} y={13.8} width={16.5} height={40.3} /><rect x={0.3} y={24.8} width={5.5} height={18.3} />
        <rect x={88.2} y={13.8} width={16.5} height={40.3} /><rect x={99.2} y={24.8} width={5.5} height={18.3} />
      </svg>
    </div>
  )
}

function Split({ label, home, away }: { label: string; home: number; away: number }) {
  return (
    <div>
      <div className="grid grid-cols-[3rem_1fr_3rem] items-baseline tabular-nums"><b>{home}%</b><span className="text-muted-foreground text-center text-xs">{label}</span><b className="text-right">{away}%</b></div>
      <div className="mt-1 flex h-2 overflow-hidden rounded-full"><div style={{ width: `${home}%`, background: TEAM_COLORS[0] }} /><div className="flex-1" style={{ background: TEAM_COLORS[1] }} /></div>
    </div>
  )
}

function Dots({ value, max, color, reverse }: { value: number; max: number; color: string; reverse?: boolean }) {
  const f = max > 0 ? (5 * value) / max : 0
  const dots = Array.from({ length: 5 }, (_, i) => Math.max(0, Math.min(1, f - i)))
  return (
    <span className={`flex gap-[3px] ${reverse ? "flex-row-reverse" : ""}`} aria-hidden>
      {dots.map((d, i) => (
        <span key={i} className="size-3 rounded-full border" style={{ borderColor: color, background: d >= 0.75 ? color : d >= 0.25 ? `linear-gradient(${reverse ? 270 : 90}deg, ${color} 50%, transparent 50%)` : "transparent" }} />
      ))}
    </span>
  )
}

const fmt = (v: number, unit: string) => (unit === "%" ? `${v}%` : unit === " m" ? `${Math.round(v)}` : Number.isInteger(v) ? String(v) : v.toFixed(2))

export function MatchReport({ recap, codes }: { recap: Recap; codes: string[] }) {
  const { heat, tilt, metrics } = recap.report
  const [h, a] = codes
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Match report</CardTitle><p className="text-muted-foreground text-xs">Where the game was played, and how each team played it.</p></CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="text-muted-foreground mb-1 flex justify-between text-[11px]"><span className="flex items-center gap-1"><i className="size-2 rounded-full" style={{ background: TEAM_COLORS[0] }} />{recap.stats[h].name} attack →</span><span>← {recap.stats[a].name} attack<i className="ml-1 inline-block size-2 rounded-full" style={{ background: TEAM_COLORS[1] }} /></span></div>
          <TerritoryMap heat={heat} />
          <p className="text-muted-foreground mt-1.5 text-center text-[11px]">Territory: shading shows which side had more touches in each part of the pitch.</p>
        </div>
        <div className="space-y-3">
          <Split label="Possession" home={recap.stats[h].possession_pct} away={recap.stats[a].possession_pct} />
          <Split label="Field tilt (share of final-third passing)" home={tilt[h]} away={tilt[a]} />
        </div>
        <div className="space-y-3 pt-1">
          {metrics.map((m) => {
            const max = Math.max(m.home, m.away), hLead = m.home >= m.away, aLead = m.away >= m.home
            return (
              <div key={m.key}>
                <div className="text-muted-foreground mb-1 text-center text-xs">{m.label}</div>
                <div className="flex items-center justify-between gap-2">
                  <Dots value={m.home} max={max} color={TEAM_COLORS[0]} reverse />
                  <span className="grid min-w-11 place-items-center rounded-full border px-2 py-0.5 text-sm font-bold tabular-nums" style={hLead ? { background: TEAM_COLORS[0], borderColor: TEAM_COLORS[0], color: "#04121c" } : { borderColor: TEAM_COLORS[0] }}>{fmt(m.home, m.unit)}</span>
                  <span className="grid min-w-11 place-items-center rounded-full border px-2 py-0.5 text-sm font-bold tabular-nums" style={aLead ? { background: TEAM_COLORS[1], borderColor: TEAM_COLORS[1], color: "#fff" } : { borderColor: TEAM_COLORS[1] }}>{fmt(m.away, m.unit)}</span>
                  <Dots value={m.away} max={max} color={TEAM_COLORS[1]} />
                </div>
              </div>
            )
          })}
        </div>
        <p className="text-muted-foreground text-[11px] leading-snug">Start distance: average metres from own goal where a possession begins. Progression: share of completed passes that gain 10+ units. Circulation: passes per possession. Build-ups: 6+ pass moves reaching the final third. Fast breaks: final third within 20 s of winning the ball deep. High press: defensive actions in the opposition half.</p>
      </CardContent>
    </Card>
  )
}

export function MatchReportPlaceholder() {
  return (
    <Card size="sm" className="border-dashed">
      <CardContent className="text-muted-foreground flex items-center gap-3 text-sm">
        <Lock className="size-4 shrink-0" />
        <span>The full match report (territory heatmap, field tilt and style metrics) unlocks at full time.</span>
      </CardContent>
    </Card>
  )
}
