import { useEffect, useRef } from "react"
import type { BenchPick, BenchState, Frames, Selected, Staff, TacticsMap } from "@/lib/types"
import { BADGE_COLORS, TEAM_COLORS, teamRgb } from "@/lib/theme"
import { isDeadBall, lastName, phaseLabel } from "@/lib/ball"

type Props = {
  frames: React.MutableRefObject<Frames>
  tactics: TacticsMap
  codes: string[]
  names: string[][]
  nums: number[][]
  layers: string[]
  focus: string[]
  selected: Selected
  onSelect: (s: Selected) => void
  view3d: boolean
  staff: Staff[]
  bench: BenchState
  onBench: (b: BenchPick) => void
  benchSel: BenchPick
}

const GW = 44, GH = 28

function hull(pts: number[][]): number[][] {
  const p = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1])
  if (p.length < 3) return p
  const cr = (o: number[], a: number[], b: number[]) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
  const lo: number[][] = [], up: number[][] = []
  for (const q of p) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q) }
  for (const q of p.slice().reverse()) { while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q) }
  return lo.slice(0, -1).concat(up.slice(0, -1))
}

export function PitchCanvas(props: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const live = useRef(props)
  live.current = props

  useEffect(() => {
    const cv = ref.current!
    const g = cv.getContext("2d")!
    const ctrl = document.createElement("canvas")
    ctrl.width = GW; ctrl.height = GH
    const cg = ctrl.getContext("2d")!
    let W = 300, H = 195, Hp = 195, mg = 9, pw = 282, ph = 182, raf = 0, last = 0
    let cur: number[][] | null = null, curBall = [50, 50]
    const X = (x: number) => mg + (x / 100) * pw, Y = (y: number) => mg + (y / 100) * ph, M = (m: number) => (m * pw) / 105
    const cl = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v))

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = cv.clientWidth; mg = W * 0.03; pw = W - 2 * mg; ph = (pw * 68) / 105; Hp = ph + 2 * mg; H = live.current.view3d ? W * 0.625 : Hp + (W * 9.5) / 105
      cv.width = W * dpr; cv.height = H * dpr
      g.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    const ro = new ResizeObserver(resize); ro.observe(cv); resize()

    const flag2D = (cx: number, cy: number, sx: number, sy: number) => {
      const h = M(2.2)
      g.save(); g.strokeStyle = "#e2e8f0"; g.lineWidth = 1.2; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx, cy - h); g.stroke()
      g.fillStyle = "#facc15"; g.beginPath(); g.moveTo(cx, cy - h); g.lineTo(cx + sx * M(1.5), cy - h + M(0.5)); g.lineTo(cx, cy - h + M(1)); g.closePath(); g.fill()
      g.strokeStyle = "rgba(255,255,255,.9)"; g.lineWidth = 1.6; g.beginPath()
      const a0 = sx > 0 ? (sy > 0 ? 0 : -Math.PI / 2) : sy > 0 ? Math.PI / 2 : Math.PI
      g.arc(cx, cy, M(1), a0, a0 + Math.PI / 2); g.stroke(); g.restore()
    }
    const pitch = () => {
      // outside the lines: out of play, darker; inside: the playing surface
      g.fillStyle = "#04120a"; g.fillRect(0, 0, W, Hp)
      g.fillStyle = "rgba(255,255,255,.04)"
      for (let i = -Hp; i < W; i += 10) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i + Hp, Hp); g.lineWidth = 1; g.strokeStyle = "rgba(255,255,255,.035)"; g.stroke() }
      g.fillStyle = "#0b2a1b"; g.fillRect(mg, mg, pw, ph)
      for (let i = 0; i < 12; i++) { g.fillStyle = i % 2 ? "rgba(255,255,255,.025)" : "rgba(0,0,0,.05)"; g.fillRect(mg + (i * pw) / 12, mg, pw / 12, ph) }
      g.strokeStyle = "rgba(255,255,255,.45)"; g.lineWidth = 1.2
      g.beginPath(); g.moveTo(X(50), Y(0)); g.lineTo(X(50), Y(100)); g.stroke()
      g.beginPath(); g.arc(X(50), Y(50), M(9.15), 0, 7); g.stroke()
      const bh = (ph * 40.3) / 68, sh = (ph * 18.3) / 68
      g.strokeRect(X(0), Y(50) - bh / 2, M(16.5), bh); g.strokeRect(X(0), Y(50) - sh / 2, M(5.5), sh)
      g.strokeRect(X(100) - M(16.5), Y(50) - bh / 2, M(16.5), bh); g.strokeRect(X(100) - M(5.5), Y(50) - sh / 2, M(5.5), sh)
      g.strokeStyle = "rgba(255,255,255,.92)"; g.lineWidth = 2.2; g.strokeRect(mg, mg, pw, ph)  // the boundary lines
      flag2D(X(0), Y(0), 1, 1); flag2D(X(100), Y(0), -1, 1); flag2D(X(0), Y(100), 1, -1); flag2D(X(100), Y(100), -1, -1)
    }

    const control = (pos: number[][]) => {
      const img = cg.createImageData(GW, GH), s2 = 2 * 8 * 8
      let k = 0
      for (let j = 0; j < GH; j++) for (let i = 0; i < GW; i++) {
        const px = ((i + 0.5) / GW) * 100, py = ((j + 0.5) / GH) * 100
        let a = 0, b = 0
        for (let n = 0; n < 22; n++) {
          const dx = (px - pos[n][0]) * 1.05, dy = (py - pos[n][1]) * 0.68, w = Math.exp(-(dx * dx + dy * dy) / s2)
          if (n < 11) a += w; else b += w
        }
        const v = (a - b) / (a + b + 0.02), cov = Math.min(1, (a + b) * 1.1), col = v > 0 ? teamRgb(0) : teamRgb(1)
        img.data[k++] = col[0]; img.data[k++] = col[1]; img.data[k++] = col[2]; img.data[k++] = Math.abs(v) * cov * 120
      }
      cg.putImageData(img, 0, 0)
    }


    // Classic football: white ball, black pentagon patches, spins as it moves
    const pentagon = (cx: number, cy: number, rad: number, rot: number) => {
      g.beginPath()
      for (let i = 0; i < 5; i++) { const a = rot + (i * 2 * Math.PI) / 5 - Math.PI / 2; i ? g.lineTo(cx + rad * Math.cos(a), cy + rad * Math.sin(a)) : g.moveTo(cx + rad * Math.cos(a), cy + rad * Math.sin(a)) }
      g.closePath()
    }
    const drawBall = (x: number, y: number, r: number, spin: number) => {
      g.save(); g.beginPath(); g.arc(x, y, r, 0, 7); g.clip()
      const gr = g.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.1, x, y, r)
      gr.addColorStop(0, "#ffffff"); gr.addColorStop(1, "#c9ced8"); g.fillStyle = gr; g.fillRect(x - r, y - r, 2 * r, 2 * r)
      g.strokeStyle = "rgba(60,60,70,.55)"; g.lineWidth = Math.max(0.6, r * 0.08)
      for (let i = 0; i < 5; i++) { const a = spin + (i * 2 * Math.PI) / 5 - Math.PI / 2; g.beginPath(); g.moveTo(x + r * 0.42 * Math.cos(a), y + r * 0.42 * Math.sin(a)); g.lineTo(x + r * 0.78 * Math.cos(a), y + r * 0.78 * Math.sin(a)); g.stroke() }
      g.fillStyle = "#14141a"; pentagon(x, y, r * 0.44, spin); g.fill()
      for (let i = 0; i < 5; i++) {
        const a = spin + (i * 2 * Math.PI) / 5 - Math.PI / 2 + Math.PI / 5
        pentagon(x + r * 0.98 * Math.cos(a), y + r * 0.98 * Math.sin(a), r * 0.4, a + Math.PI / 2 + Math.PI); g.fill()
      }
      g.restore()
      g.strokeStyle = "rgba(20,20,26,.85)"; g.lineWidth = Math.max(0.8, r * 0.07); g.beginPath(); g.arc(x, y, r, 0, 7); g.stroke()
    }

    // Who has the ball: solid ring + name (confirmed), dashed ring + "name?" (likely), dashed ring on the ball (unknown).
    // Dead balls get a pulsing ring and a label that falls back from "Throw-in" to "Set piece" when unsure.
    const pill = (text: string, x: number, y: number, color: string) => {
      g.font = "700 9px system-ui"; g.textAlign = "center"; g.textBaseline = "middle"
      const w = g.measureText(text).width + 10
      g.fillStyle = "rgba(7,11,20,.88)"; g.beginPath(); g.roundRect(x - w / 2, y - 7, w, 14, 7); g.fill()
      g.fillStyle = color; g.fillText(text, x, y + 0.5)
    }
    const holderMarks = (ts: number, fr: Frames, codes: string[], names: string[][], at: (t: number, n: number) => number[], ballPt: number[], tagLift: number) => {
      const pulse = 1 + Math.sin(ts / 220) * 0.1, amber = "#fbbf24"
      const t = codes.indexOf(fr.holder ? fr.holder[0] : fr.poss)
      if (fr.holder && fr.band > 0) {
        const [x, y, r] = at(t, fr.holder[1])
        g.save(); g.lineWidth = 2.4; g.strokeStyle = amber
        if (fr.band === 1) g.setLineDash([3, 3])
        g.beginPath(); g.arc(x, y, (r + 5) * pulse, 0, 7); g.stroke(); g.restore()
        pill(lastName(names[t]?.[fr.holder[1]] ?? "") + (fr.band === 1 ? "?" : ""), x, y - r - tagLift, amber)
      } else {
        g.save(); g.setLineDash([3, 3]); g.lineWidth = 1.8; g.strokeStyle = TEAM_COLORS[Math.max(0, t)]
        g.beginPath(); g.arc(ballPt[0], ballPt[1], ballPt[2] + 7 * pulse, 0, 7); g.stroke(); g.restore()
      }
      const label = phaseLabel(fr.phase, fr.phaseBand)
      if (label) {
        if (isDeadBall(fr.phase)) {
          g.save(); g.lineWidth = 2; g.strokeStyle = TEAM_COLORS[Math.max(0, t)] + "cc"; g.beginPath(); g.arc(ballPt[0], ballPt[1], ballPt[2] + 10 * pulse, 0, 7); g.stroke(); g.restore()
        }
        pill(label.toUpperCase(), ballPt[0], ballPt[1] + ballPt[2] + 14, "#e2e8f0")
      }
    }

    // Ball path: separate arrows for the last touches, newest bright, oldest nearly gone
    const arrow = (x0: number, y0: number, x1: number, y1: number, a: number) => {
      const ang = Math.atan2(y1 - y0, x1 - x0), w = 1.4 + 2.2 * a, hs = 4 + 5 * a
      g.strokeStyle = `rgba(255,255,255,${0.12 + 0.8 * a})`; g.fillStyle = g.strokeStyle; g.lineWidth = w; g.lineCap = "round"
      g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1 - Math.cos(ang) * hs * 0.6, y1 - Math.sin(ang) * hs * 0.6); g.stroke()
      g.beginPath(); g.moveTo(x1, y1)
      g.lineTo(x1 - hs * Math.cos(ang - 0.45), y1 - hs * Math.sin(ang - 0.45)); g.lineTo(x1 - hs * Math.cos(ang + 0.45), y1 - hs * Math.sin(ang + 0.45))
      g.closePath(); g.fill()
    }
    const trailArrows = (tr: number[][], map: (p: number[]) => number[]) => {
      const pts = tr.map(map)
      for (let i = 1; i < pts.length; i++) arrow(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], i / (pts.length - 1))
    }

    // ---------- officials, offside lines and restart cues ----------
    const ofc = { r: [50, 50], a1: 25, a2: 75 }
    type Officials = { R: number[]; A1: number[]; A2: number[]; lineL: number; lineR: number; active: number }
    const officials = (cur: number[][], ball: number[], dt: number): Officials => {
      const { codes, frames } = live.current
      const fr = frames.current
      const dir = fr.poss === codes[1] ? -1 : 1  // team 0 attacks right (+x)
      const dead = isDeadBall(fr.phase)
      // Diagonal system: about 15 m behind play and off to the side of it, never on top of the ball or a player.
      const side = ball[1] < 50 ? 1 : -1  // the infield side of the ball
      const tx = ball[0] - dir * 14
      const ty = dead ? ball[1] + side * 16 : ball[1] + side * 18 + (50 - ball[1]) * 0.15
      const kr = 1 - Math.exp(-dt * 1.8), ka = 1 - Math.exp(-dt * 3)
      ofc.r[0] += (cl(tx, 4, 96) - ofc.r[0]) * kr; ofc.r[1] += (cl(ty, 6, 94) - ofc.r[1]) * kr
      const keepAway = (from: number[], minM: number) => {  // push the referee out to minM metres from a point
        const dx = (ofc.r[0] - from[0]) * 1.05, dy = (ofc.r[1] - from[1]) * 0.68, d = Math.hypot(dx, dy)
        if (d >= minM) return
        const [ux, uy] = d > 1e-3 ? [dx / d, dy / d] : [-dir, 0]
        ofc.r[0] = cl(from[0] + (ux * minM) / 1.05, 2, 98); ofc.r[1] = cl(from[1] + (uy * minM) / 0.68, 3, 97)
      }
      keepAway(ball, dead ? 10 : 12)
      for (let pass = 0; pass < 2; pass++) for (const p of cur) keepAway(p, 4)
      keepAway(ball, dead ? 10 : 12)
      const xs0 = cur.slice(0, 11).map((p) => p[0]).sort((a, b) => a - b), xs1 = cur.slice(11).map((p) => p[0]).sort((a, b) => b - a)
      const lineL = Math.min(xs0[1], 50), lineR = Math.max(xs1[1], 50)  // second-last defender; no offside in your own half
      ofc.a1 += (Math.max(2, lineL) - ofc.a1) * ka; ofc.a2 += (Math.min(98, lineR) - ofc.a2) * ka
      return { R: [ofc.r[0], ofc.r[1]], A1: [ofc.a1, -1.6], A2: [ofc.a2, 101.6], lineL, lineR, active: fr.poss === codes[1] ? 0 : 1 }
    }
    const lineCol = (i: number) => (i === 0 ? TEAM_COLORS[1] : TEAM_COLORS[0])  // the attackers the line holds back

    // The dead-ball cue: the touchline stretch for a throw-in, the corner arc for a corner
    const cuePoints = (fr: Frames, ball: number[]): { kind: string; pts: number[][] } | null => {
      if (fr.phase === "throw_in") {
        const y = ball[1] < 50 ? 0 : 100, d = 8 / 1.05
        return { kind: "throw", pts: [[cl(ball[0] - d, 0, 100), y], [cl(ball[0] + d, 0, 100), y]] }
      }
      if (fr.phase === "corner") {
        const cx = ball[0] > 50 ? 100 : 0, cy = ball[1] > 50 ? 100 : 0
        const a0 = cx === 0 ? (cy === 0 ? 0 : -Math.PI / 2) : cy === 0 ? Math.PI / 2 : Math.PI
        const pts = Array.from({ length: 13 }, (_, i) => { const a = a0 + (i / 12) * (Math.PI / 2); return [cx + (cx === 0 ? 1 : -1) * 0 + (3.5 / 1.05) * Math.cos(a), cy + (3.5 / 0.68) * Math.sin(a)] })
        return { kind: "corner", pts }
      }
      return null
    }

    // ---------- 3D camera ----------
    const cam = { psi: 0, alpha: 0.8, dragged: false }
    const heads: number[][] = new Array(22).fill(0).map(() => [-99, -99, 0])
    const D = 120
    let F = 1, CX = 0, CY = 0
    const project = (wx: number, wy: number, wz: number, psi: number): number[] => {
      const c = Math.cos(psi), sn = Math.sin(psi), ca = Math.cos(cam.alpha), sa = Math.sin(cam.alpha)
      const x = wx * c - wy * sn, y = wx * sn + wy * c
      const depth = y * sa - wz * ca + D
      const k = F / depth
      return [CX + x * k, CY - (y * ca + wz * sa) * k, depth, k]
    }
    const fit = (psi: number) => {
      F = 1; CX = 0; CY = 0
      const pts = [[-56, -37.5, 0], [56, -37.5, 0], [56, 37.5, 0], [-56, 37.5, 0], [-56, 0, 6], [56, 0, 6], [-40, -44, 0], [40, -44, 0]]
      const pr = pts.map((p) => project(p[0], p[1], p[2], psi))
      const xs = pr.map((p) => p[0]), ys = pr.map((p) => p[1])
      const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
      F = Math.min((W * 0.96) / (maxX - minX), (H * 0.94) / (maxY - minY))
      CX = W / 2 - (F * (minX + maxX)) / 2; CY = H / 2 - (F * (minY + maxY)) / 2
    }
    const w3 = (x: number, y: number) => [(x / 100 - 0.5) * 105, (y / 100 - 0.5) * 68]
    const poly = (pts: number[][], fill?: string, stroke?: string, lw = 1) => {
      g.beginPath(); pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.closePath()
      if (fill) { g.fillStyle = fill; g.fill() }
      if (stroke) { g.strokeStyle = stroke; g.lineWidth = lw; g.stroke() }
    }
    const line3 = (pts: number[][], psi: number, z = 0.03) => {
      g.beginPath(); pts.forEach((p, i) => { const q = project(p[0], p[1], z, psi); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]) }); g.stroke()
    }
    const goal3 = (end: number, psi: number) => {
      const x = end * 52.5, hw = 3.66, hh = 2.44, back = end * 2.2
      const a = project(x, -hw, 0, psi), b = project(x, -hw, hh, psi), c = project(x, hw, hh, psi), d = project(x, hw, 0, psi)
      const a2 = project(x + back, -hw, 0, psi), b2 = project(x + back, -hw, hh, psi), c2 = project(x + back, hw, hh, psi), d2 = project(x + back, hw, 0, psi)
      poly([b, c, c2, b2], "rgba(255,255,255,.08)"); poly([a, b, b2, a2], "rgba(255,255,255,.06)"); poly([d, c, c2, d2], "rgba(255,255,255,.06)")
      g.strokeStyle = "rgba(255,255,255,.9)"; g.lineWidth = 2
      g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.lineTo(c[0], c[1]); g.lineTo(d[0], d[1]); g.stroke()
    }

    const draw3D = (ts: number, cur: number[][] | null, curBall: number[], of: Officials | null) => {
      const { tactics, codes, names, layers, focus, selected, frames } = live.current
      const fr = frames.current
      const psi = cam.psi + (cam.dragged ? 0 : 0.09 * Math.sin(ts / 3500))
      fit(psi)
      // backdrop
      const dark = document.documentElement.classList.contains("dark")
      const bg = g.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, dark ? "#050914" : "#ffffff"); bg.addColorStop(1, dark ? "#0a1a2b" : "#e8edf3")
      g.fillStyle = bg; g.fillRect(0, 0, W, H)
      const glow = project(0, 0, 0, psi); const rg = g.createRadialGradient(glow[0], glow[1], 10, glow[0], glow[1], W * 0.7)
      rg.addColorStop(0, dark ? "rgba(56,189,248,.16)" : "rgba(0,255,133,.26)"); rg.addColorStop(1, "rgba(56,189,248,0)"); g.fillStyle = rg; g.fillRect(0, 0, W, H)
      // slab sides
      const cs = [[-56, -37.5], [56, -37.5], [56, 37.5], [-56, 37.5]]
      for (let i = 0; i < 4; i++) {
        const a = cs[i], b = cs[(i + 1) % 4]
        poly([project(a[0], a[1], 0, psi), project(b[0], b[1], 0, psi), project(b[0], b[1], -2, psi), project(a[0], a[1], -2, psi)], "#06120c")
      }
      // out-of-play run-off around the lines
      poly([project(-56, -37.5, 0, psi), project(56, -37.5, 0, psi), project(56, 37.5, 0, psi), project(-56, 37.5, 0, psi)], "#082514")
      // grass stripes
      for (let i = 0; i < 14; i++) {
        const x0 = -52.5 + i * 7.5, x1 = x0 + 7.5
        poly([project(x0, -34, 0, psi), project(x1, -34, 0, psi), project(x1, 34, 0, psi), project(x0, 34, 0, psi)], i % 2 ? "#0f4a2c" : "#115c34")
      }
      // markings
      g.strokeStyle = "rgba(255,255,255,.55)"; g.lineWidth = 1.4
      line3([[0, -34], [0, 34]], psi)
      line3(Array.from({ length: 49 }, (_, i) => [9.15 * Math.cos((i / 48) * 6.2832), 9.15 * Math.sin((i / 48) * 6.2832)]), psi)
      for (const e of [-1, 1]) {
        line3([[e * 52.5, -20.2], [e * 36, -20.2], [e * 36, 20.2], [e * 52.5, 20.2]], psi)
        line3([[e * 52.5, -9.2], [e * 47, -9.2], [e * 47, 9.2], [e * 52.5, 9.2]], psi)
      }
      g.strokeStyle = "rgba(255,255,255,.95)"; g.lineWidth = 2.6  // the boundary lines: in play or out
      line3([[-52.5, -34], [52.5, -34], [52.5, 34], [-52.5, 34], [-52.5, -34]], psi, 0.05)
      for (const cx of [-52.5, 52.5]) for (const cy of [-34, 34]) {  // corner flags and quarter circles
        const sx = cx < 0 ? 1 : -1, sy = cy < 0 ? 1 : -1, a0 = sx > 0 ? (sy > 0 ? 0 : -Math.PI / 2) : sy > 0 ? Math.PI / 2 : Math.PI
        g.lineWidth = 1.6; line3(Array.from({ length: 9 }, (_, i) => [cx + 1 * Math.cos(a0 + (i / 8) * (Math.PI / 2)), cy + 1 * Math.sin(a0 + (i / 8) * (Math.PI / 2))]), psi, 0.05)
        const b0 = project(cx, cy, 0, psi), b1 = project(cx, cy, 1.6, psi), b2 = project(cx + sx * 0.9, cy, 1.4, psi), b3 = project(cx, cy, 1.2, psi)
        g.strokeStyle = "#e2e8f0"; g.lineWidth = 1.4; g.beginPath(); g.moveTo(b0[0], b0[1]); g.lineTo(b1[0], b1[1]); g.stroke()
        poly([b1, b2, b3], "#facc15")
      }
      const cue = cuePoints(fr, curBall)
      if (cue) {
        g.save(); g.strokeStyle = "#fbbf24"; g.lineWidth = 4; g.lineCap = "round"; g.setLineDash([9, 6]); g.lineDashOffset = -ts / 40
        line3(cue.pts.map((p) => w3(p[0], p[1])), psi, 0.08); g.restore()
      }
      // far goal first
      const gFar = project(52.5, 0, 0, psi)[2] > project(-52.5, 0, 0, psi)[2] ? 1 : -1
      goal3(gFar, psi)

      if (cur) {
        // territory as terrain: height = dominance
        if (layers.includes("control")) {
          const NX = 36, NY = 24, hgt: number[][] = [], val: number[][] = []
          for (let j = 0; j <= NY; j++) { hgt.push([]); val.push([]) }
          for (let j = 0; j <= NY; j++) for (let i = 0; i <= NX; i++) {
            const px = (i / NX) * 100, py = (j / NY) * 100
            let a = 0, b = 0
            for (let n = 0; n < 22; n++) { const dx = (px - cur[n][0]) * 1.05, dy = (py - cur[n][1]) * 0.68, w = Math.exp(-(dx * dx + dy * dy) / 128); if (n < 11) a += w; else b += w }
            const v = (a - b) / (a + b + 0.02), cov = Math.min(1, (a + b) * 1.1)
            val[j][i] = v * cov; hgt[j][i] = v * cov * 4.5
          }
          const order = [] as number[]; for (let j = NY - 1; j >= 0; j--) order.push(j)
          const flip = psi > 0 ? 1 : 1
          for (const j of order) for (let ii = 0; ii < NX; ii++) {
            const i = flip ? ii : NX - 1 - ii
            const v = (val[j][i] + val[j][i + 1] + val[j + 1][i] + val[j + 1][i + 1]) / 4, al = Math.min(0.6, Math.abs(v) * 0.75)
            if (al < 0.05) continue
            const P = (ci: number, cj: number) => { const w = w3((ci / NX) * 100, (cj / NY) * 100); return project(w[0], w[1], Math.max(0, hgt[cj][ci]) * (hgt[cj][ci] > 0 ? 1 : 0.35) , psi) }
            poly([P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)], `rgba(${teamRgb(v > 0 ? 0 : 1).join(",")},${al})`)
          }
        }
        // hulls on the ground
        if (layers.includes("shape")) [0, 1].forEach((t) => {
          const pts: number[][] = []
          for (let n = 1; n < 11; n++) { const w = w3(cur[t * 11 + n][0], cur[t * 11 + n][1]); pts.push([w[0], w[1]]) }
          const h = hull(pts); if (h.length < 3) return
          poly(h.map((p) => project(p[0], p[1], 0.1, psi)), TEAM_COLORS[t] + "26", TEAM_COLORS[t] + "dd", 2)
        })
        if (layers.includes("trail") && fr.trail.length > 1) trailArrows(fr.trail, (p) => { const w = w3(p[0], p[1]); return project(w[0], w[1], 0.4, psi) })
        if (of && layers.includes("offside")) [[of.lineL, 0], [of.lineR, 1]].forEach(([x, i]) => {
          const act = of.active === i, xm = w3(x, 0)[0]
          g.save(); g.setLineDash([8, 6]); g.strokeStyle = lineCol(i); g.globalAlpha = act ? 0.95 : 0.35; g.lineWidth = act ? 2.4 : 1.2
          line3([[xm, -34], [xm, 34]], psi, 0.06); g.restore()
          if (act) { const q = project(xm, 34, 0.5, psi); pill("OFFSIDE LINE", q[0], q[1] - 8, lineCol(i)) }
        })
        // players, far to near
        type T = { t: number; n: number; gp: number[] }
        const list: T[] = []
        for (let t = 0; t < 2; t++) for (let n = 0; n < 11; n++) { const w = w3(cur[t * 11 + n][0], cur[t * 11 + n][1]); list.push({ t, n, gp: project(w[0], w[1], 0, psi) }) }
        list.sort((a, b) => b.gp[2] - a.gp[2])
        for (const { t, n, gp } of list) {
          const w = w3(cur[t * 11 + n][0], cur[t * 11 + n][1]), hd = project(w[0], w[1], 3.4, psi)
          const r = Math.max(5, 2.1 * gp[3]), sel = selected && selected.team === t && selected.idx === n
          g.fillStyle = "rgba(0,0,0,.35)"; g.beginPath(); g.ellipse(gp[0], gp[1], r * 1.2, r * 0.5, 0, 0, 7); g.fill()
          g.strokeStyle = TEAM_COLORS[t] + "aa"; g.lineWidth = 2; g.beginPath(); g.moveTo(gp[0], gp[1]); g.lineTo(hd[0], hd[1]); g.stroke()
          if (sel) { g.strokeStyle = "#fbbf24"; g.lineWidth = 2; g.beginPath(); g.ellipse(gp[0], gp[1], r * 1.7 + Math.sin(ts / 200) * 1.5, r * 0.8, 0, 0, 7); g.stroke() }
          g.beginPath(); g.arc(hd[0], hd[1], r, 0, 7); g.fillStyle = TEAM_COLORS[t]; g.fill()
          g.lineWidth = n === 0 ? 2.5 : 1.5; g.strokeStyle = n === 0 ? "#fbbf24" : "#fff"; g.stroke()
          const no = String(live.current.nums[t]?.[n] ?? n + 1)
          g.fillStyle = "#04121c"; g.font = `700 ${Math.round(r * (no.length > 1 ? 0.85 : 1.05))}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle"
          g.fillText(no, hd[0], hd[1] + 0.5)
          heads[t * 11 + n] = [hd[0], hd[1], r]
          const role = layers.includes("roles") && focus.includes(codes[t]) && n > 0 ? tactics[codes[t]]?.roles[n] : undefined
          if (role) {
            const f = Math.round(Math.max(8, r * 0.95)); g.font = `800 ${f}px system-ui`
            const bw = g.measureText(role.short).width + 8
            g.fillStyle = "rgba(7,11,20,.88)"; g.beginPath(); g.roundRect(hd[0] - bw / 2, hd[1] - r - f - 6, bw, f + 4, 5); g.fill()
            g.fillStyle = BADGE_COLORS[role.short] ?? "#fff"; g.fillText(role.short, hd[0], hd[1] - r - f / 2 - 4)
          }
        }
        if (of) {
          const rw = w3(of.R[0], of.R[1]); stand3(rw[0], rw[1], 3.4, psi, "#111827", "#facc15", "R", "#facc15", 1, 1.05)
          for (const a of [of.A1, of.A2]) { const aw = w3(a[0], a[1]); stand3(aw[0], aw[1], 3.2, psi, "#facc15", "#111827", "AR", "#111827", 1, 0.95) }
        }
        // ball
        const bw = w3(curBall[0], curBall[1]), bg2 = project(bw[0], bw[1], 0, psi), bp = project(bw[0], bw[1], 1.1, psi), br = Math.max(5.5, 1.7 * bg2[3])
        g.fillStyle = "rgba(0,0,0,.4)"; g.beginPath(); g.ellipse(bg2[0], bg2[1], br * 1.1, br * 0.5, 0, 0, 7); g.fill()
        g.beginPath(); g.arc(bp[0], bp[1], br + 3, 0, 7); g.fillStyle = "rgba(255,255,255,.22)"; g.fill()
        drawBall(bp[0], bp[1], br, (curBall[0] + curBall[1]) * 0.12)
        holderMarks(ts, fr, codes, names, (t, n) => heads[t * 11 + n], [bp[0], bp[1], br], 24)
      }
      drawBench3D(ts, psi)
      goal3(-gFar, psi)
    }

    const mouse = { x: 0, y: 0, down: false, moved: 0 }
    const onDown = (e: PointerEvent) => { mouse.x = e.clientX; mouse.y = e.clientY; mouse.down = true; mouse.moved = 0 }
    const onMove = (e: PointerEvent) => {
      if (!mouse.down || !live.current.view3d) return
      const dx = e.clientX - mouse.x, dy = e.clientY - mouse.y
      mouse.moved += Math.abs(dx) + Math.abs(dy); mouse.x = e.clientX; mouse.y = e.clientY
      if (mouse.moved > 6) { cam.dragged = true; cam.psi = Math.max(-0.8, Math.min(0.8, cam.psi + dx * 0.006)); cam.alpha = Math.max(0.5, Math.min(1.3, cam.alpha - dy * 0.005)) }
    }
    const onUp = () => { mouse.down = false }
    const onDbl = () => { cam.dragged = false; cam.psi = 0; cam.alpha = 0.8 }
    cv.addEventListener("pointermove", onMove); window.addEventListener("pointerup", onUp); cv.addEventListener("dblclick", onDbl)
    cv.addEventListener("pointerdown", onDown)

    // ---------- technical areas: dugouts, coaches, subs ----------
    const benchHeads: { x: number; y: number; r: number; pick: NonNullable<BenchPick> }[] = []
    const token = (x: number, y: number, r: number, fill: string, stroke: string, label: string, alpha = 1, ink = "#04121c") => {
      g.save(); g.globalAlpha = alpha
      g.beginPath(); g.arc(x, y, r, 0, 7); g.fillStyle = fill; g.fill(); g.lineWidth = 1.5; g.strokeStyle = stroke; g.stroke()
      if (label) { g.fillStyle = ink; g.font = `700 ${Math.max(7, Math.round(r))}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(label, x, y + 0.5) }
      g.restore()
    }
    const coachX = [-1, -1]
    const bounce = (fr: Frames, code: string) => {
      const dt = fr.goal && fr.goal.team === code ? performance.now() - fr.goal.at : 1e9
      return dt < 2600 ? Math.abs(Math.sin(dt / 150)) * 7 * (1 - dt / 2600) : 0
    }
    const subRole = (st: Staff, i: number, state: "seat" | "warm" | "used") =>
      `Substitute #${st.subs[i].number} · ${state === "warm" ? "warming up" : state === "used" ? "now on the pitch" : st.subs[i].pos}`

    // Ring around the selected substitute / coach so it is clear who is picked
    const benchRing = (ts: number) => {
      const sb = live.current.benchSel
      if (!sb) return
      const h = benchHeads.find((x) => x.pick.team === sb.team && x.pick.name === sb.name)
      if (!h) return
      g.save(); g.strokeStyle = "#fbbf24"; g.lineWidth = 2.4
      g.beginPath(); g.arc(h.x, h.y, Math.max(8, h.r - 1) + Math.sin(ts / 200) * 1.2, 0, 7); g.stroke(); g.restore()
    }

    const drawBench2D = (ts: number) => {
      const { staff, bench, codes, frames } = live.current
      const fr = frames.current, top = Hp, strip = H - Hp
      const gr = g.createLinearGradient(0, top, 0, H); gr.addColorStop(0, "#0a2417"); gr.addColorStop(1, "#06150d")
      g.fillStyle = gr; g.fillRect(0, top, W, strip)
      g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 1.2; g.beginPath(); g.moveTo(0, top); g.lineTo(W, top); g.stroke()
      benchHeads.length = 0
      const rs = Math.max(4.5, Math.min(7, strip * 0.2))
      for (let t = 0; t < 2; t++) {
        const st = staff[t]; if (!st) continue
        const x0 = (t ? 0.54 : 0.05) * W, x1 = (t ? 0.95 : 0.46) * W, col = TEAM_COLORS[t], b = bench[codes[t]] ?? { warming: [], used: [] }
        g.fillStyle = "rgba(255,255,255,.06)"; g.strokeStyle = col + "88"; g.lineWidth = 1.2
        g.beginPath(); g.roundRect(x0, top + strip * 0.5, x1 - x0, strip * 0.46, 6); g.fill(); g.stroke()
        g.font = "700 8px system-ui"; g.textAlign = "left"; g.textBaseline = "alphabetic"; g.fillStyle = col; g.fillText(`${codes[t]} BENCH`, x0 + 4, top + strip * 0.5 - 3)
        const n = st.subs.length
        st.subs.forEach((sb, i) => {
          const sx = x0 + 10 + ((i + 0.5) * (x1 - x0 - 20)) / n, sy = top + strip * 0.74
          if (b.warming.includes(i)) {
            const jx = (x0 + x1) / 2 + Math.sin(ts / 500 + t * 2) * (x1 - x0) * 0.34, jy = top + strip * 0.26
            token(sx, sy, rs, "transparent", col + "66", "", 0.6)
            token(jx, jy, rs, col, "#fff", String(sb.number))
            g.font = "800 7px system-ui"; g.textAlign = "center"; g.fillStyle = "#e2e8f0"; g.fillText("WARM-UP", jx, jy - rs - 3)
            benchHeads.push({ x: jx, y: jy, r: rs + 5, pick: { team: t, name: sb.name, role: subRole(st, i, "warm") } })
          } else if (b.used.includes(i)) {
            token(sx, sy, rs, "#64748b", "#94a3b8", "", 0.25)
            benchHeads.push({ x: sx, y: sy, r: rs + 3, pick: { team: t, name: sb.name, role: subRole(st, i, "used") } })
          } else {
            token(sx, sy, rs, col, "#ffffffaa", String(sb.number), 0.62)
            benchHeads.push({ x: sx, y: sy, r: rs + 3, pick: { team: t, name: sb.name, role: subRole(st, i, "seat") } })
          }
        })
        // coaching staff stand on the technical-area line; the head coach shadows the ball along the touchline
        const target = (x0 + x1) / 2 + (fr.ball[0] / 100 - 0.5) * (x1 - x0) * 0.14  // stays inside the technical area
        coachX[t] = coachX[t] < 0 ? target : coachX[t] + (target - coachX[t]) * 0.06
        const cy = top + strip * 0.3, lift = bounce(fr, codes[t])
        token(coachX[t], cy - lift, rs * 1.2, "#0f172a", "#fbbf24", "HC", 1, "#fbbf24")
        benchHeads.push({ x: coachX[t], y: cy - lift, r: rs + 6, pick: { team: t, name: st.coach, role: "Head coach" } })
      }
      g.beginPath(); g.roundRect(W / 2 - 16, top + strip * 0.34, 32, strip * 0.34, 4); g.fillStyle = "rgba(255,255,255,.12)"; g.fill()
      g.font = "700 7px system-ui"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillStyle = "#cbd5e1"; g.fillText("4TH OFFICIAL", W / 2, top + strip * 0.51)
      benchRing(ts)
    }

    const stand3 = (wx: number, wy: number, headZ: number, psi: number, fill: string, stroke: string, label: string, ink: string, alpha = 1, sc = 1) => {
      const gp = project(wx, wy, 0, psi), hd = project(wx, wy, headZ, psi), r = Math.max(4.5, 1.7 * gp[3] * sc)
      g.save(); g.globalAlpha = alpha
      g.fillStyle = "rgba(0,0,0,.35)"; g.beginPath(); g.ellipse(gp[0], gp[1], r * 1.1, r * 0.45, 0, 0, 7); g.fill()
      g.strokeStyle = stroke + "aa"; g.lineWidth = 1.6; g.beginPath(); g.moveTo(gp[0], gp[1]); g.lineTo(hd[0], hd[1]); g.stroke()
      g.beginPath(); g.arc(hd[0], hd[1], r, 0, 7); g.fillStyle = fill; g.fill(); g.lineWidth = 1.4; g.strokeStyle = stroke; g.stroke()
      if (label) { g.fillStyle = ink; g.font = `700 ${Math.max(7, Math.round(r))}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(label, hd[0], hd[1] + 0.5) }
      g.restore()
      return [hd[0], hd[1], r]
    }

    const drawBench3D = (ts: number, psi: number) => {
      const { staff, bench, codes, frames } = live.current
      const fr = frames.current
      benchHeads.length = 0
      for (let t = 0; t < 2; t++) {
        const st = staff[t]; if (!st) continue
        const xc = t ? 24 : -24, half = 15, col = TEAM_COLORS[t], b = bench[codes[t]] ?? { warming: [], used: [] }
        poly([project(xc - half, -37, 0, psi), project(xc + half, -37, 0, psi), project(xc + half, -43, 0, psi), project(xc - half, -43, 0, psi)], col + "22", col + "99", 1.2)
        poly([project(xc - half, -43, 0, psi), project(xc + half, -43, 0, psi), project(xc + half, -43, 3.2, psi), project(xc - half, -43, 3.2, psi)], col + "16", col + "66", 1)
        poly([project(xc - half, -40.2, 0.9, psi), project(xc + half, -40.2, 0.9, psi), project(xc + half, -41.6, 0.9, psi), project(xc - half, -41.6, 0.9, psi)], "rgba(148,163,184,.45)")
        const n = st.subs.length
        st.subs.forEach((sb, i) => {
          const sx = xc - half + 1.8 + (i * (2 * half - 3.6)) / (n - 1)
          if (b.warming.includes(i)) {
            const jx = xc + Math.sin(ts / 500 + t * 2) * half * 0.9
            const h = stand3(jx, -35.4, 3.2, psi, col, "#fff", String(sb.number), "#04121c")
            g.font = "800 8px system-ui"; g.textAlign = "center"; g.fillStyle = "#e2e8f0"; g.fillText("WARM-UP", h[0], h[1] - h[2] - 3)
            benchHeads.push({ x: h[0], y: h[1], r: h[2] + 5, pick: { team: t, name: sb.name, role: subRole(st, i, "warm") } })
          } else {
            const used = b.used.includes(i)
            const h = stand3(sx, -40.9, 2.6, psi, used ? "#64748b" : col, used ? "#94a3b8" : "#ffffffaa", used ? "" : String(sb.number), "#04121c", used ? 0.3 : 0.75, 0.85)
            benchHeads.push({ x: h[0], y: h[1], r: h[2] + 3, pick: { team: t, name: sb.name, role: subRole(st, i, used ? "used" : "seat") } })
          }
        })
        const target = xc + (fr.ball[0] / 100 - 0.5) * 6  // a few steps either side of the dugout centre
        coachX[t] = coachX[t] < 0 ? target : coachX[t] + (target - coachX[t]) * 0.06
        const lift = bounce(fr, codes[t]) * 0.35
        const ch = stand3(coachX[t], -35.6, 3.6 + lift, psi, "#0f172a", "#fbbf24", "HC", "#fbbf24", 1, 1.15)
        benchHeads.push({ x: ch[0], y: ch[1], r: ch[2] + 6, pick: { team: t, name: st.coach, role: "Head coach" } })
      }
      benchRing(ts)
    }

    const draw = (ts: number) => {
      const { frames, tactics, codes, names, layers, focus, selected } = live.current
      const fr = frames.current
      const dt = Math.min(0.1, (ts - last) / 1000 || 0.016); last = ts
      g.clearRect(0, 0, W, H)
      if (fr.reset) { cur = null; fr.reset = false }
      if (!cur && fr.target) { cur = fr.target.map((p) => p.slice()); curBall = fr.ball.slice() }
      if (cur && fr.target) {
        const k = 1 - Math.exp(-dt * 6)
        for (let n = 0; n < 22; n++) { cur[n][0] += (fr.target[n][0] - cur[n][0]) * k; cur[n][1] += (fr.target[n][1] - cur[n][1]) * k }
        const kb = Math.min(1, k * 1.6)
        curBall[0] += (fr.ball[0] - curBall[0]) * kb; curBall[1] += (fr.ball[1] - curBall[1]) * kb
      }
      const of = cur ? officials(cur, curBall, dt) : null
      if (live.current.view3d) { draw3D(ts, cur, curBall, of); raf = requestAnimationFrame(draw); return }
      pitch(); drawBench2D(ts)
      if (cur && fr.target) {
        if (layers.includes("control")) { control(cur); g.imageSmoothingEnabled = true; g.drawImage(ctrl, mg, mg, pw, ph) }
        if (layers.includes("shape")) [0, 1].forEach((t) => {
          const pts: number[][] = []
          for (let n = 1; n < 11; n++) pts.push([X(cur![t * 11 + n][0]), Y(cur![t * 11 + n][1])])
          const h = hull(pts); if (h.length < 3) return
          g.beginPath(); h.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.closePath()
          g.fillStyle = TEAM_COLORS[t] + "1f"; g.fill(); g.strokeStyle = TEAM_COLORS[t] + "cc"; g.lineWidth = 1.6; g.lineJoin = "round"; g.stroke()
        })
        if (layers.includes("trail") && fr.trail.length > 1) trailArrows(fr.trail, (p) => [X(p[0]), Y(p[1])])
        const cue = cuePoints(fr, curBall)
        if (cue) {
          g.save(); g.strokeStyle = "#fbbf24"; g.lineWidth = 4; g.lineCap = "round"; g.setLineDash([9, 6]); g.lineDashOffset = -ts / 40
          g.beginPath(); cue.pts.forEach((p, i) => (i ? g.lineTo(X(p[0]), Y(p[1])) : g.moveTo(X(p[0]), Y(p[1])))); g.stroke(); g.restore()
        }
        if (of && layers.includes("offside")) [[of.lineL, 0], [of.lineR, 1]].forEach(([x, i]) => {
          const act = of.active === i
          g.save(); g.setLineDash([6, 5]); g.strokeStyle = lineCol(i); g.globalAlpha = act ? 0.95 : 0.35; g.lineWidth = act ? 2 : 1
          g.beginPath(); g.moveTo(X(x), Y(0)); g.lineTo(X(x), Y(100)); g.stroke(); g.restore()
          if (act) pill("OFFSIDE LINE", cl(X(x), 40, W - 40), Y(0) + 12, lineCol(i))
        })
        const r = Math.max(6, Math.min(11, W * 0.018))
        for (let t = 0; t < 2; t++) for (let n = 0; n < 11; n++) {
          const x = X(cur[t * 11 + n][0]), y = Y(cur[t * 11 + n][1]), sel = selected && selected.team === t && selected.idx === n
          g.beginPath(); g.arc(x, y, r, 0, 7); g.fillStyle = TEAM_COLORS[t]; g.fill()
          g.lineWidth = n === 0 ? 2.5 : 1.5; g.strokeStyle = n === 0 ? "#fbbf24" : "#fff"; g.stroke()
          if (sel) { g.beginPath(); g.arc(x, y, r + 4 + Math.sin(ts / 200) * 1.5, 0, 7); g.strokeStyle = "#fbbf24"; g.lineWidth = 2; g.stroke() }
          const no = String(live.current.nums[t]?.[n] ?? n + 1)
          g.fillStyle = "#04121c"; g.font = `700 ${Math.round(r * (no.length > 1 ? 0.85 : 1.05))}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle"
          g.fillText(no, x, y + 0.5)
          heads[t * 11 + n] = [x, y, r]
          const role = layers.includes("roles") && focus.includes(codes[t]) && n > 0 ? tactics[codes[t]]?.roles[n] : undefined
          if (role) {
            const f = Math.round(Math.max(8, r * 0.95)); g.font = `800 ${f}px system-ui`
            const w = g.measureText(role.short).width + 8
            g.fillStyle = "rgba(7,11,20,.85)"; g.beginPath(); g.roundRect(x - w / 2, y + r + 2, w, f + 4, 5); g.fill()
            g.fillStyle = BADGE_COLORS[role.short] ?? "#fff"; g.fillText(role.short, x, y + r + 2 + (f + 4) / 2 + 0.5)
          }
        }
        if (of) {
          const orr = Math.max(5.5, r * 0.95)
          token(X(of.R[0]), Y(of.R[1]), orr, "#111827", "#facc15", "R", 1, "#facc15")
          for (const a of [of.A1, of.A2]) token(X(a[0]), Y(a[1]), orr * 0.92, "#facc15", "#111827", "AR", 1, "#111827")
          const fl = fr.flag
          if (fl && ts - fl.at < 3500) {  // offside: the assistant on that half raises the flag for ~3 s
            const right = fl.team === codes[0]  // team 0 attacks right, so the right-half AR flags them
            const a = right ? of.A2 : of.A1, ax = X(a[0]), ay = Y(a[1]), up = a[1] > 50 ? -1 : 1
            const lx = fl.x ?? (right ? of.lineR : of.lineL)
            g.save(); g.strokeStyle = "#ef4444"; g.lineWidth = 2.5; g.setLineDash([]); g.globalAlpha = 0.9
            g.beginPath(); g.moveTo(X(lx), Y(0)); g.lineTo(X(lx), Y(100)); g.stroke(); g.restore()
            const top = ay + up * orr * 3.2
            g.strokeStyle = "#e5e7eb"; g.lineWidth = 2; g.beginPath(); g.moveTo(ax + orr, ay); g.lineTo(ax + orr, top); g.stroke()
            const wave = Math.sin(ts / 90) * 2
            g.fillStyle = "#ef4444"; g.fillRect(ax + orr, top - (up < 0 ? 0 : orr * 1.3), orr * 1.6 + wave, orr * 1.3)
            g.fillStyle = "#facc15"; g.fillRect(ax + orr, top - (up < 0 ? 0 : orr * 1.3), (orr * 1.6 + wave) / 2, orr * 0.65)
            pill(`OFFSIDE · ${fl.player.split(" ").slice(-1)[0]}`, cl(X(lx), 60, W - 60), Y(50), "#ef4444")
          }
        }
        const bx = X(curBall[0]), by = Y(curBall[1])
        const brr = Math.max(5.5, r * 0.85)
        g.beginPath(); g.arc(bx, by, brr + 3, 0, 7); g.fillStyle = "rgba(255,255,255,.22)"; g.fill()
        drawBall(bx, by, brr, (curBall[0] + curBall[1]) * 0.12)
        holderMarks(ts, fr, codes, names, (t, n) => heads[t * 11 + n], [bx, by, brr], 12)
      }
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)

    const pick = (e: PointerEvent) => {
      if (mouse.moved > 6) return
      const rect = cv.getBoundingClientRect(), mx = e.clientX - rect.left, my = e.clientY - rect.top
      const hit = benchHeads.find((h) => Math.hypot(h.x - mx, h.y - my) <= h.r + 4)
      if (hit) { live.current.onBench(hit.pick); return }
      live.current.onBench(null)
      let best: Selected = null, bd = 28
      if (!cur) return
      for (let i = 0; i < 22; i++) { const d = Math.hypot(heads[i][0] - mx, heads[i][1] - my); if (d < bd) { bd = d; best = { team: i < 11 ? 0 : 1, idx: i % 11 } } }
      live.current.onSelect(best)
    }
    cv.addEventListener("pointerup", pick)
    return () => { cancelAnimationFrame(raf); ro.disconnect(); cv.removeEventListener("pointerup", pick); cv.removeEventListener("pointerdown", onDown); cv.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onUp); cv.removeEventListener("dblclick", onDbl) }
  }, [])

  return <canvas ref={ref} className={`block w-full touch-manipulation ${props.view3d ? "aspect-[16/10] cursor-grab" : "aspect-[105/79.7]"}`} />
}
