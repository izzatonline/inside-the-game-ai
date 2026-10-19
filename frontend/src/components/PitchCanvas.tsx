import { useEffect, useRef } from "react"
import type { Frames, Selected, TacticsMap } from "@/lib/types"
import { BADGE_COLORS, TEAM_COLORS } from "@/lib/theme"

type Props = {
  frames: React.MutableRefObject<Frames>
  tactics: TacticsMap
  codes: string[]
  layers: string[]
  focus: string[]
  selected: Selected
  onSelect: (s: Selected) => void
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
    let W = 300, H = 195, raf = 0, last = 0
    let cur: number[][] | null = null, curBall = [50, 50]
    const X = (x: number) => (x / 100) * W, Y = (y: number) => (y / 100) * H, M = (m: number) => (m * W) / 105

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = cv.clientWidth; H = (W * 68) / 105
      cv.width = W * dpr; cv.height = H * dpr
      g.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    const ro = new ResizeObserver(resize); ro.observe(cv); resize()

    const pitch = () => {
      g.fillStyle = "#0b2a1b"; g.fillRect(0, 0, W, H)
      for (let i = 0; i < 12; i++) { g.fillStyle = i % 2 ? "rgba(255,255,255,.025)" : "rgba(0,0,0,.05)"; g.fillRect((i * W) / 12, 0, W / 12, H) }
      g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 1.2; g.strokeRect(1, 1, W - 2, H - 2)
      g.beginPath(); g.moveTo(W / 2, 0); g.lineTo(W / 2, H); g.stroke()
      g.beginPath(); g.arc(W / 2, H / 2, M(9.15), 0, 7); g.stroke()
      const bh = (H * 40.3) / 68, sh = (H * 18.3) / 68
      g.strokeRect(1, H / 2 - bh / 2, M(16.5), bh); g.strokeRect(1, H / 2 - sh / 2, M(5.5), sh)
      g.strokeRect(W - 1 - M(16.5), H / 2 - bh / 2, M(16.5), bh); g.strokeRect(W - 1 - M(5.5), H / 2 - sh / 2, M(5.5), sh)
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
        const v = (a - b) / (a + b + 0.02), cov = Math.min(1, (a + b) * 1.1), col = v > 0 ? [56, 189, 248] : [244, 63, 94]
        img.data[k++] = col[0]; img.data[k++] = col[1]; img.data[k++] = col[2]; img.data[k++] = Math.abs(v) * cov * 120
      }
      cg.putImageData(img, 0, 0)
    }

    const draw = (ts: number) => {
      const { frames, tactics, codes, layers, focus, selected } = live.current
      const fr = frames.current
      const dt = Math.min(0.1, (ts - last) / 1000 || 0.016); last = ts
      g.clearRect(0, 0, W, H); pitch()
      if (fr.reset) { cur = null; fr.reset = false }
      if (!cur && fr.target) { cur = fr.target.map((p) => p.slice()); curBall = fr.ball.slice() }
      if (cur && fr.target) {
        const k = 1 - Math.exp(-dt * 6)
        for (let n = 0; n < 22; n++) { cur[n][0] += (fr.target[n][0] - cur[n][0]) * k; cur[n][1] += (fr.target[n][1] - cur[n][1]) * k }
        const kb = Math.min(1, k * 1.6)
        curBall[0] += (fr.ball[0] - curBall[0]) * kb; curBall[1] += (fr.ball[1] - curBall[1]) * kb
        if (layers.includes("control")) { control(cur); g.imageSmoothingEnabled = true; g.drawImage(ctrl, 0, 0, W, H) }
        if (layers.includes("shape")) [0, 1].forEach((t) => {
          const pts: number[][] = []
          for (let n = 1; n < 11; n++) pts.push([X(cur![t * 11 + n][0]), Y(cur![t * 11 + n][1])])
          const h = hull(pts); if (h.length < 3) return
          g.beginPath(); h.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.closePath()
          g.fillStyle = TEAM_COLORS[t] + "1f"; g.fill(); g.strokeStyle = TEAM_COLORS[t] + "cc"; g.lineWidth = 1.6; g.lineJoin = "round"; g.stroke()
        })
        if (layers.includes("trail") && fr.trail.length > 1) {
          g.strokeStyle = "rgba(255,255,255,.35)"; g.lineWidth = 2; g.beginPath()
          fr.trail.forEach((p, i) => (i ? g.lineTo(X(p[0]), Y(p[1])) : g.moveTo(X(p[0]), Y(p[1])))); g.stroke()
        }
        const r = Math.max(6, Math.min(11, W * 0.018))
        for (let t = 0; t < 2; t++) for (let n = 0; n < 11; n++) {
          const x = X(cur[t * 11 + n][0]), y = Y(cur[t * 11 + n][1]), sel = selected && selected.team === t && selected.idx === n
          g.beginPath(); g.arc(x, y, r, 0, 7); g.fillStyle = TEAM_COLORS[t]; g.fill()
          g.lineWidth = n === 0 ? 2.5 : 1.5; g.strokeStyle = n === 0 ? "#fbbf24" : "#fff"; g.stroke()
          if (sel) { g.beginPath(); g.arc(x, y, r + 4 + Math.sin(ts / 200) * 1.5, 0, 7); g.strokeStyle = "#fbbf24"; g.lineWidth = 2; g.stroke() }
          g.fillStyle = "#04121c"; g.font = `700 ${Math.round(r * 1.05)}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle"
          g.fillText(String(n + 1), x, y + 0.5)
          const role = layers.includes("roles") && focus.includes(codes[t]) && n > 0 ? tactics[codes[t]]?.roles[n] : undefined
          if (role) {
            const f = Math.round(Math.max(8, r * 0.95)); g.font = `800 ${f}px system-ui`
            const w = g.measureText(role.short).width + 8
            g.fillStyle = "rgba(7,11,20,.85)"; g.beginPath(); g.roundRect(x - w / 2, y + r + 2, w, f + 4, 5); g.fill()
            g.fillStyle = BADGE_COLORS[role.short] ?? "#fff"; g.fillText(role.short, x, y + r + 2 + (f + 4) / 2 + 0.5)
          }
        }
        const bx = X(curBall[0]), by = Y(curBall[1])
        g.beginPath(); g.arc(bx, by, r * 0.55 + 3, 0, 7); g.fillStyle = "rgba(255,255,255,.25)"; g.fill()
        g.beginPath(); g.arc(bx, by, r * 0.5, 0, 7); g.fillStyle = "#fff"; g.fill()
      }
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)

    const pick = (e: PointerEvent) => {
      if (!cur) return
      const rect = cv.getBoundingClientRect(), mx = e.clientX - rect.left, my = e.clientY - rect.top
      let best: Selected = null, bd = 26
      for (let t = 0; t < 2; t++) for (let n = 0; n < 11; n++) {
        const d = Math.hypot(X(cur[t * 11 + n][0]) - mx, Y(cur[t * 11 + n][1]) - my)
        if (d < bd) { bd = d; best = { team: t, idx: n } }
      }
      live.current.onSelect(best)
    }
    cv.addEventListener("pointerdown", pick)
    return () => { cancelAnimationFrame(raf); ro.disconnect(); cv.removeEventListener("pointerdown", pick) }
  }, [])

  return <canvas ref={ref} className="block aspect-[105/68] w-full touch-manipulation" />
}
