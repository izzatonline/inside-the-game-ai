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
  view3d: boolean
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
      W = cv.clientWidth; H = live.current.view3d ? W * 0.625 : (W * 68) / 105
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
      const pts = [[-52.5, -34, 0], [52.5, -34, 0], [52.5, 34, 0], [-52.5, 34, 0], [-52.5, 0, 6], [52.5, 0, 6]]
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

    const draw3D = (ts: number, cur: number[][] | null, curBall: number[]) => {
      const { tactics, codes, layers, focus, selected, frames } = live.current
      const fr = frames.current
      const psi = cam.psi + (cam.dragged ? 0 : 0.09 * Math.sin(ts / 3500))
      fit(psi)
      // backdrop
      const bg = g.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, "#050914"); bg.addColorStop(1, "#0a1a2b")
      g.fillStyle = bg; g.fillRect(0, 0, W, H)
      const glow = project(0, 0, 0, psi); const rg = g.createRadialGradient(glow[0], glow[1], 10, glow[0], glow[1], W * 0.7)
      rg.addColorStop(0, "rgba(56,189,248,.16)"); rg.addColorStop(1, "rgba(56,189,248,0)"); g.fillStyle = rg; g.fillRect(0, 0, W, H)
      // slab sides
      const cs = [[-52.5, -34], [52.5, -34], [52.5, 34], [-52.5, 34]]
      for (let i = 0; i < 4; i++) {
        const a = cs[i], b = cs[(i + 1) % 4]
        poly([project(a[0], a[1], 0, psi), project(b[0], b[1], 0, psi), project(b[0], b[1], -2, psi), project(a[0], a[1], -2, psi)], "#06120c")
      }
      // grass stripes
      for (let i = 0; i < 14; i++) {
        const x0 = -52.5 + i * 7.5, x1 = x0 + 7.5
        poly([project(x0, -34, 0, psi), project(x1, -34, 0, psi), project(x1, 34, 0, psi), project(x0, 34, 0, psi)], i % 2 ? "#0f4a2c" : "#115c34")
      }
      // markings
      g.strokeStyle = "rgba(255,255,255,.55)"; g.lineWidth = 1.4
      line3([[-52.5, -34], [52.5, -34], [52.5, 34], [-52.5, 34], [-52.5, -34]], psi); line3([[0, -34], [0, 34]], psi)
      line3(Array.from({ length: 49 }, (_, i) => [9.15 * Math.cos((i / 48) * 6.2832), 9.15 * Math.sin((i / 48) * 6.2832)]), psi)
      for (const e of [-1, 1]) {
        line3([[e * 52.5, -20.2], [e * 36, -20.2], [e * 36, 20.2], [e * 52.5, 20.2]], psi)
        line3([[e * 52.5, -9.2], [e * 47, -9.2], [e * 47, 9.2], [e * 52.5, 9.2]], psi)
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
            poly([P(i, j), P(i + 1, j), P(i + 1, j + 1), P(i, j + 1)], v > 0 ? `rgba(56,189,248,${al})` : `rgba(244,63,94,${al})`)
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
          g.fillStyle = "#04121c"; g.font = `700 ${Math.round(r * 1.05)}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle"
          g.fillText(String(n + 1), hd[0], hd[1] + 0.5)
          heads[t * 11 + n] = [hd[0], hd[1], r]
          const role = layers.includes("roles") && focus.includes(codes[t]) && n > 0 ? tactics[codes[t]]?.roles[n] : undefined
          if (role) {
            const f = Math.round(Math.max(8, r * 0.95)); g.font = `800 ${f}px system-ui`
            const bw = g.measureText(role.short).width + 8
            g.fillStyle = "rgba(7,11,20,.88)"; g.beginPath(); g.roundRect(hd[0] - bw / 2, hd[1] - r - f - 6, bw, f + 4, 5); g.fill()
            g.fillStyle = BADGE_COLORS[role.short] ?? "#fff"; g.fillText(role.short, hd[0], hd[1] - r - f / 2 - 4)
          }
        }
        // ball
        const bw = w3(curBall[0], curBall[1]), bg2 = project(bw[0], bw[1], 0, psi), bp = project(bw[0], bw[1], 1.1, psi), br = Math.max(5.5, 1.7 * bg2[3])
        g.fillStyle = "rgba(0,0,0,.4)"; g.beginPath(); g.ellipse(bg2[0], bg2[1], br * 1.1, br * 0.5, 0, 0, 7); g.fill()
        g.beginPath(); g.arc(bp[0], bp[1], br + 3, 0, 7); g.fillStyle = "rgba(255,255,255,.22)"; g.fill()
        drawBall(bp[0], bp[1], br, (curBall[0] + curBall[1]) * 0.12)
      }
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

    const draw = (ts: number) => {
      const { frames, tactics, codes, layers, focus, selected } = live.current
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
      if (live.current.view3d) { draw3D(ts, cur, curBall); raf = requestAnimationFrame(draw); return }
      pitch()
      if (cur && fr.target) {
        if (layers.includes("control")) { control(cur); g.imageSmoothingEnabled = true; g.drawImage(ctrl, 0, 0, W, H) }
        if (layers.includes("shape")) [0, 1].forEach((t) => {
          const pts: number[][] = []
          for (let n = 1; n < 11; n++) pts.push([X(cur![t * 11 + n][0]), Y(cur![t * 11 + n][1])])
          const h = hull(pts); if (h.length < 3) return
          g.beginPath(); h.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.closePath()
          g.fillStyle = TEAM_COLORS[t] + "1f"; g.fill(); g.strokeStyle = TEAM_COLORS[t] + "cc"; g.lineWidth = 1.6; g.lineJoin = "round"; g.stroke()
        })
        if (layers.includes("trail") && fr.trail.length > 1) trailArrows(fr.trail, (p) => [X(p[0]), Y(p[1])])
        const r = Math.max(6, Math.min(11, W * 0.018))
        for (let t = 0; t < 2; t++) for (let n = 0; n < 11; n++) {
          const x = X(cur[t * 11 + n][0]), y = Y(cur[t * 11 + n][1]), sel = selected && selected.team === t && selected.idx === n
          g.beginPath(); g.arc(x, y, r, 0, 7); g.fillStyle = TEAM_COLORS[t]; g.fill()
          g.lineWidth = n === 0 ? 2.5 : 1.5; g.strokeStyle = n === 0 ? "#fbbf24" : "#fff"; g.stroke()
          if (sel) { g.beginPath(); g.arc(x, y, r + 4 + Math.sin(ts / 200) * 1.5, 0, 7); g.strokeStyle = "#fbbf24"; g.lineWidth = 2; g.stroke() }
          g.fillStyle = "#04121c"; g.font = `700 ${Math.round(r * 1.05)}px system-ui`; g.textAlign = "center"; g.textBaseline = "middle"
          g.fillText(String(n + 1), x, y + 0.5)
          heads[t * 11 + n] = [x, y, r]
          const role = layers.includes("roles") && focus.includes(codes[t]) && n > 0 ? tactics[codes[t]]?.roles[n] : undefined
          if (role) {
            const f = Math.round(Math.max(8, r * 0.95)); g.font = `800 ${f}px system-ui`
            const w = g.measureText(role.short).width + 8
            g.fillStyle = "rgba(7,11,20,.85)"; g.beginPath(); g.roundRect(x - w / 2, y + r + 2, w, f + 4, 5); g.fill()
            g.fillStyle = BADGE_COLORS[role.short] ?? "#fff"; g.fillText(role.short, x, y + r + 2 + (f + 4) / 2 + 0.5)
          }
        }
        const bx = X(curBall[0]), by = Y(curBall[1])
        const brr = Math.max(5.5, r * 0.85)
        g.beginPath(); g.arc(bx, by, brr + 3, 0, 7); g.fillStyle = "rgba(255,255,255,.22)"; g.fill()
        drawBall(bx, by, brr, (curBall[0] + curBall[1]) * 0.12)
      }
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)

    const pick = (e: PointerEvent) => {
      if (!cur || mouse.moved > 6) return
      const rect = cv.getBoundingClientRect(), mx = e.clientX - rect.left, my = e.clientY - rect.top
      let best: Selected = null, bd = 28
      for (let i = 0; i < 22; i++) { const d = Math.hypot(heads[i][0] - mx, heads[i][1] - my); if (d < bd) { bd = d; best = { team: i < 11 ? 0 : 1, idx: i % 11 } } }
      live.current.onSelect(best)
    }
    cv.addEventListener("pointerup", pick)
    return () => { cancelAnimationFrame(raf); ro.disconnect(); cv.removeEventListener("pointerup", pick); cv.removeEventListener("pointerdown", onDown); cv.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onUp); cv.removeEventListener("dblclick", onDbl) }
  }, [])

  return <canvas ref={ref} className={`block w-full touch-manipulation ${props.view3d ? "aspect-[16/10] cursor-grab" : "aspect-[105/68]"}`} />
}
