import { useEffect, useRef, useState } from "react"
import type { Frames, Overlay, Recap, Settings, Stats, TacticsMap } from "@/lib/types"

export type Toast = { id: number; title: string; body: string; goal: boolean }

export function useMatchStream(settings: Settings, runId: number) {
  const frames = useRef<Frames>({ target: null, ball: [50, 50], trail: [], n: 0, reset: true })
  const latest = useRef(settings)
  latest.current = settings
  const [stats, setStats] = useState<Stats | null>(null)
  const [tactics, setTactics] = useState<TacticsMap>({})
  const [overlays, setOverlays] = useState<Overlay[]>([])
  const [recap, setRecap] = useState<Recap | null>(null)
  const [status, setStatus] = useState("Connecting…")
  const [toast, setToast] = useState<Toast | null>(null)

  useEffect(() => {
    const s = latest.current
    frames.current = { target: null, ball: [50, 50], trail: [], n: 0, reset: true }
    setStats(null); setTactics({}); setOverlays([]); setRecap(null); setStatus("Reading shape…"); setToast(null)
    const player = s.player.split(":")[2] ?? ""
    const q = new URLSearchParams({ seed: s.seed, speed: s.speed, lang: s.lang, mode: s.mode, team: s.team, player, metric: s.metric })
    const es = new EventSource(`/api/${s.src}?${q}`)
    let toastId = 0
    const show = (title: string, body: string, goal: boolean) => setToast({ id: ++toastId, title, body, goal })
    es.addEventListener("frame", (e) => {
      const f = JSON.parse((e as MessageEvent).data) as { pos: number[][]; ball: number[] }
      const fr = frames.current
      fr.target = f.pos; fr.ball = f.ball
      if (fr.n++ % 2 === 0) { fr.trail.push(f.ball.slice()); if (fr.trail.length > 14) fr.trail.shift() }
    })
    es.addEventListener("stats", (e) => setStats(JSON.parse((e as MessageEvent).data)))
    es.addEventListener("tactics", (e) => { setTactics(JSON.parse((e as MessageEvent).data)); setStatus("AI shape analysis live") })
    es.addEventListener("overlay", (e) => {
      const o = JSON.parse((e as MessageEvent).data) as Overlay
      setOverlays((prev) => [o, ...prev].slice(0, 40))
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

  return { frames, stats, tactics, overlays, recap, status, toast }
}
