import { useEffect, useRef, useState } from "react"
import type { BallInfo, Band } from "@/lib/ball"
import type { Frames, Overlay, Recap, Settings, Stats, TacticsMap } from "@/lib/types"

export type Toast = { id: number; title: string; body: string; goal: boolean }

export function useMatchStream(settings: Settings, runId: number) {
  const frames = useRef<Frames>({ target: null, ball: [50, 50], trail: [], n: 0, reset: true, holder: null, band: 0, phase: "open", phaseBand: 2, poss: "", lastConfirmed: null })
  const latest = useRef(settings)
  latest.current = settings
  const [stats, setStats] = useState<Stats | null>(null)
  const [tactics, setTactics] = useState<TacticsMap>({})
  const [overlays, setOverlays] = useState<Overlay[]>([])
  const [recap, setRecap] = useState<Recap | null>(null)
  const [status, setStatus] = useState("Connecting…")
  const [toast, setToast] = useState<Toast | null>(null)
  const [ball, setBall] = useState<BallInfo | null>(null)
  const [series, setSeries] = useState<{ minute: number; value: number }[]>([])
  const [goals, setGoals] = useState<{ minute: number; team: string }[]>([])

  useEffect(() => {
    const s = latest.current
    frames.current = { target: null, ball: [50, 50], trail: [], n: 0, reset: true, holder: null, band: 0, phase: "open", phaseBand: 2, poss: "", lastConfirmed: null }
    setBall(null); setSeries([]); setGoals([]); setStats(null); setTactics({}); setOverlays([]); setRecap(null); setStatus("Reading shape…"); setToast(null)
    const player = s.player.split(":")[2] ?? ""
    const q = new URLSearchParams({ seed: s.seed, speed: s.speed, lang: s.lang, mode: s.mode, team: s.team, player, metric: s.metric })
    const es = new EventSource(`/api/${s.src}?${q}`)
    let toastId = 0
    let lastKey = ""
    const acc = new Map<number, { sum: number; n: number }>()
    const show = (title: string, body: string, goal: boolean) => setToast({ id: ++toastId, title, body, goal })
    es.addEventListener("frame", (e) => {
      const f = JSON.parse((e as MessageEvent).data) as {
        pos: number[][]; ball: number[]; poss: string; holder: [string, number] | null; conf: number; phase: string; phase_conf: number
      }
      const fr = frames.current
      fr.target = f.pos; fr.ball = f.ball
      fr.n++
      const last = fr.trail[fr.trail.length - 1]
      if (!last || Math.hypot((f.ball[0] - last[0]) * 1.05, (f.ball[1] - last[1]) * 0.68) > 4) {
        fr.trail.push(f.ball.slice()); if (fr.trail.length > 5) fr.trail.shift()  // last 4 touches
      }
      // Confidence bands; hold a confirmed holder ~0.9 s so the marker does not flicker.
      const now = performance.now()
      let band: Band = f.conf >= 0.8 ? 2 : f.conf >= 0.5 ? 1 : 0
      const h = f.holder
      if (h && band === 2) fr.lastConfirmed = { team: h[0], idx: h[1], at: now }
      else if (h && fr.lastConfirmed && fr.lastConfirmed.team === h[0] && fr.lastConfirmed.idx === h[1] && now - fr.lastConfirmed.at < 900) band = 2
      const phaseBand: Band = f.phase_conf >= 0.8 ? 2 : f.phase_conf >= 0.5 ? 1 : 0
      fr.holder = band === 0 ? null : h; fr.band = band; fr.phase = f.phase; fr.phaseBand = phaseBand; fr.poss = f.poss
      const key = `${f.poss}|${fr.holder?.[1] ?? -1}|${band}|${f.phase}|${phaseBand}`
      if (key !== lastKey) { lastKey = key; setBall({ poss: f.poss, holder: fr.holder, band, phase: f.phase, phaseBand }) }
    })
    es.addEventListener("stats", (e) => {
      const st = JSON.parse((e as MessageEvent).data) as Stats
      setStats(st)
      const b = acc.get(st.minute) ?? { sum: 0, n: 0 }
      b.sum += st.momentum; b.n++; acc.set(st.minute, b)
      setSeries(Array.from(acc, ([minute, v]) => ({ minute, value: v.sum / v.n })))
    })
    es.addEventListener("tactics", (e) => { setTactics(JSON.parse((e as MessageEvent).data)); setStatus("AI shape analysis live") })
    es.addEventListener("overlay", (e) => {
      const o = JSON.parse((e as MessageEvent).data) as Overlay
      setOverlays((prev) => [o, ...prev].slice(0, 40))
      if (o.kind === "goal") setGoals((prev) => [...prev, { minute: o.minute, team: o.team }])
      if (o.kind === "goal") show(o.headline, o.body, true)
      else if (o.kind === "tactic_shift") show(o.headline, o.body, false)
    })
    es.addEventListener("recap", (e) => {
      const r = JSON.parse((e as MessageEvent).data) as Recap
      setRecap(r); setStatus("Full time"); show(r.headline, "", false); es.close()
    })
    es.onerror = () => { setStatus("Disconnected"); es.close() }
    return () => es.close()
  }, [runId])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 4200)
    return () => clearTimeout(t)
  }, [toast])

  return { frames, stats, tactics, overlays, recap, status, toast, ball, series, goals }
}
