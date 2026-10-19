import { useEffect, useMemo, useRef, useState } from "react"
import { Activity, Box, ChevronDown, ChevronUp, Moon, PanelLeft, Settings2, Sun } from "lucide-react"
import { MomentCard } from "@/components/MomentCard"
import { MomentumChart } from "@/components/MomentumChart"
import { PitchCanvas } from "@/components/PitchCanvas"
import { SettingsSheet } from "@/components/SettingsSheet"
import { StatsPanel } from "@/components/StatsPanel"
import { LineupsPanel } from "@/components/LineupsPanel"
import { RecapCard } from "@/components/RecapCard"
import { TacticsPanel } from "@/components/TacticsPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Toggle } from "@/components/ui/toggle"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { AppSidebar } from "@/components/AppSidebar"
import { SidebarInset, SidebarProvider, useSidebar } from "@/components/ui/sidebar"
import { useMatchStream } from "@/hooks/useMatchStream"
import { fmtMinute } from "@/lib/format"
import { useTheme } from "@/hooks/useTheme"
import { describeBall } from "@/lib/ball"
import { TEAM_COLORS } from "@/lib/theme"
import type { BenchPick, Config, MatchInfo, Selected, Settings } from "@/lib/types"

const params = new URLSearchParams(location.search)
const initial: Settings = {
  match: params.get("match") ?? "", mode: params.get("mode") ?? "casual", lang: params.get("lang") ?? "en", team: params.get("team") ?? "", player: "",
  metric: params.get("metric") ?? "", src: params.get("src") ?? "stream", speed: params.get("speed") ?? "60", seed: params.get("seed") ?? "7",
}

/** True below the lg breakpoint (phones and small tablets), where the pitch can be folded away. */
function useIsMobile() {
  const [mobile, setMobile] = useState(() => window.matchMedia("(max-width: 1023px)").matches)
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)")
    const on = () => setMobile(mq.matches)
    mq.addEventListener("change", on)
    return () => mq.removeEventListener("change", on)
  }, [])
  return mobile
}

export default function App() {
  const [matches, setMatches] = useState<MatchInfo[] | null>(null)
  const [matchId, setMatchId] = useState(params.get("match") ?? "")
  const [cfg, setCfg] = useState<Config | null>(null)
  const theme = useTheme()
  useEffect(() => {
    fetch("/api/matches").then((r) => r.json()).then((list: MatchInfo[]) => { setMatches(list); setMatchId((cur) => (list.some((m) => m.id === cur) ? cur : list[0].id)) })
  }, [])
  useEffect(() => {
    if (!matchId) return
    setCfg(null)
    fetch(`/api/config?match=${matchId}`).then((r) => r.json()).then(setCfg)
  }, [matchId])
  if (!matches || !cfg) return <div className="space-y-3 p-4"><Skeleton className="h-14 w-full" /><Skeleton className="aspect-[105/77.5] w-full" /></div>
  return (
    <SidebarProvider>
      <AppSidebar matches={matches} matchId={matchId} onSelect={setMatchId} theme={theme.mode} onTheme={theme.setMode} />
      <SidebarInset className="bg-transparent">
        <Match key={matchId} cfg={cfg} matchId={matchId} theme={theme} />
      </SidebarInset>
    </SidebarProvider>
  )
}

function Match({ cfg, matchId, theme }: { cfg: Config; matchId: string; theme: ReturnType<typeof useTheme> }) {
  const codes = Object.keys(cfg.teams)
  const [draft, setDraft] = useState(initial)
  const [applied, setApplied] = useState(initial)
  const [runId, setRunId] = useState(0)
  const [open, setOpen] = useState(false)
  const [layers, setLayers] = useState(["shape", "control", "roles"])
  const [focus, setFocus] = useState(window.innerWidth < 480 ? [codes[0]] : codes)
  const [selected, setSelected] = useState<Selected>(null)
  const [view3d, setView3d] = useState(params.get("view") === "3d")
  const { frames, stats, tactics, overlays, recap, status, toast, ball, series, goals, cards, subLog, bench, roster } = useMatchStream({ ...applied, match: matchId }, runId, cfg)
  const { toggleSidebar } = useSidebar()
  const [benchSel, setBenchSel] = useState<BenchPick>(null)
  const info = ball ? describeBall(ball, cfg, codes) : null
  const narrow = useMemo(() => window.innerWidth < 480, [])
  const mobile = useIsMobile()
  const { mode: themeMode, setMode: setThemeMode, dark } = theme
  const [momentumOpen, setMomentumOpen] = useState(false)
  const [pitchHidden, setPitchHidden] = useState(false)
  const hidePitch = mobile && pitchHidden
  const pitchBox = useRef<HTMLDivElement>(null)
  const headerRef = useRef<HTMLDivElement>(null)
  useEffect(() => {  // tab bar sticks right below the (variable-height) pinned header
    const el = headerRef.current
    if (!el) return
    const set = () => document.documentElement.style.setProperty("--hdr", `${el.offsetHeight}px`)
    const ro = new ResizeObserver(set); ro.observe(el); set()
    return () => ro.disconnect()
  }, [])
  const [pitchH, setPitchH] = useState(0)
  useEffect(() => {
    const canvas = pitchBox.current?.querySelector('canvas')
    if (!canvas) return
    const ro = new ResizeObserver(() => setPitchH(canvas.offsetHeight + 2))
    ro.observe(canvas); setPitchH(canvas.offsetHeight + 2)
    return () => ro.disconnect()
  }, [view3d])

  const apply = () => {
    const [c, i] = draft.player ? draft.player.split(":") : []
    setSelected(c ? { team: codes.indexOf(c), idx: Number(i) } : null)
    setApplied(draft); setRunId((n) => n + 1); setOpen(false)
  }
  const sel = selected ? { name: (roster[codes[selected.team]] ?? cfg.teams[codes[selected.team]].players)[selected.idx], team: cfg.teams[codes[selected.team]].name, role: tactics[codes[selected.team]]?.roles[selected.idx] } : null
  const shape = codes.map((c, i) => ({ c, i, p: tactics[c] })).filter((x) => x.p)

  const controls = (
    <>
<div className="mt-2 flex max-w-full items-center gap-3 overflow-x-auto pb-1">
          <Toggle pressed={view3d} onPressedChange={setView3d} variant="outline" size="sm" aria-label="3D view"><Box /> 3D</Toggle>
          <ToggleGroup multiple value={layers} onValueChange={setLayers} variant="outline" size="sm" spacing={1}>
            <ToggleGroupItem value="shape">Team shape</ToggleGroupItem><ToggleGroupItem value="control">Territory</ToggleGroupItem>
            <ToggleGroupItem value="roles">Roles</ToggleGroupItem><ToggleGroupItem value="trail">Ball trail</ToggleGroupItem>
          </ToggleGroup>
          <ToggleGroup multiple value={focus} onValueChange={setFocus} variant="outline" size="sm" spacing={1}>
            {codes.map((c) => <ToggleGroupItem key={c} value={c}>{c}</ToggleGroupItem>)}
          </ToggleGroup>
        </div>
        <div className="text-muted-foreground mt-1.5 flex flex-wrap gap-x-4 text-xs">
          {shape.map(({ c, i, p }) => <span key={c} className="flex items-center gap-1.5"><span className="size-2 rounded-full" style={{ background: TEAM_COLORS[i] }} /><b className="text-foreground">{p.formation}</b> {p.primary}</span>)}
        </div>
    </>
  )

  return (
    <div style={{ ["--pa" as string]: view3d ? 1.6 : 1.3548 }} className="grid grid-cols-[minmax(0,1fr)] lg:grid-cols-[min(calc(100%_-_440px),calc((100dvh_-_178px)_*_var(--pa)))_minmax(0,1fr)] lg:gap-6 lg:px-5">
      <div ref={headerRef} className="bg-background/85 sticky top-0 z-30 min-w-0 border-b backdrop-blur-md px-3 pt-[calc(8px+env(safe-area-inset-top))] pb-1.5 lg:self-start lg:px-0 lg:pt-4">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-lg" aria-label="Matches menu" onClick={toggleSidebar}><PanelLeft /></Button>
          <Card size="sm" className="hover:bg-muted/40 flex-1 cursor-pointer transition-colors" role="button" tabIndex={0} aria-label="Show match momentum" onClick={() => setMomentumOpen(true)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setMomentumOpen(true) }}>
              <CardContent className="grid grid-cols-[1fr_auto_1fr] items-center">
            <div className="flex min-w-0 items-center gap-2 text-sm font-semibold"><span className="size-2.5 shrink-0 rounded-full" style={{ background: TEAM_COLORS[0] }} /><span className="truncate">{narrow ? codes[0] : cfg.teams[codes[0]].name}</span></div>
            <div className="px-3 text-center"><div className="text-2xl leading-none font-extrabold tabular-nums">{stats?.teams[codes[0]].goals ?? 0}-{stats?.teams[codes[1]].goals ?? 0}</div><div className="flex items-center justify-center gap-1 text-[11px] font-bold text-(--minute)">{fmtMinute(stats?.minute ?? 0)}'<Activity className="text-muted-foreground size-3" /></div></div>
            <div className="flex min-w-0 items-center justify-end gap-2 text-sm font-semibold"><span className="truncate">{narrow ? codes[1] : cfg.teams[codes[1]].name}</span><span className="size-2.5 shrink-0 rounded-full" style={{ background: TEAM_COLORS[1] }} /></div>
          </CardContent>
            </Card>
          {mobile && <Button variant="outline" size="icon-lg" aria-label={pitchHidden ? "Show pitch" : "Hide pitch"} aria-expanded={!pitchHidden} onClick={() => setPitchHidden((h) => !h)}>{pitchHidden ? <ChevronDown /> : <ChevronUp />}</Button>}
          <Button variant="outline" size="icon-lg" aria-label="Toggle light or dark mode" className="hidden sm:inline-flex" onClick={() => setThemeMode(dark ? "light" : "dark")}>{dark ? <Sun /> : <Moon />}</Button>
          <Button variant="outline" size="icon-lg" aria-label="Settings" onClick={() => setOpen(true)}><Settings2 /></Button>
        </div>
        <div className="my-2 h-1 overflow-hidden rounded bg-rose-500"><div className="h-full bg-sky-400 transition-all duration-500" style={{ width: `${50 + 50 * (stats?.momentum ?? 0)}%` }} /></div>
        <div ref={pitchBox} className="border-border relative overflow-hidden rounded-2xl border shadow-2xl will-change-[opacity,max-height]"
          style={mobile && pitchH ? {
            opacity: hidePitch ? 0 : 1, maxHeight: hidePitch ? 0 : pitchH, visibility: hidePitch ? "hidden" : "visible",
            transition: hidePitch ? "max-height .5s ease, opacity .4s ease, visibility 0s linear .5s" : "max-height .5s ease, opacity .4s ease, visibility 0s",
          } : undefined}>
          <PitchCanvas frames={frames} tactics={tactics} codes={codes} names={codes.map((c) => roster[c] ?? cfg.teams[c].players)} staff={codes.map((c) => cfg.teams[c].staff)} bench={bench} onBench={setBenchSel} layers={layers} focus={focus} selected={selected} onSelect={(x) => { setSelected(x); if (x) setBenchSel(null) }} view3d={view3d} />
          <Badge variant="secondary" className="absolute top-2 right-2 hidden sm:inline-flex">{status}</Badge>
          {view3d && <Badge variant="outline" className="bg-background/70 absolute top-2 right-2 text-[10px] backdrop-blur sm:top-9">Drag to rotate · double-tap to reset</Badge>}
          {toast && <div key={toast.id} className={`bg-background/90 animate-in fade-in slide-in-from-top-2 absolute top-2 left-1/2 max-w-[90%] -translate-x-1/2 rounded-xl border px-3 py-1.5 text-center backdrop-blur ${toast.goal ? "border-emerald-400" : ""}`}>
            <b className="block text-sm whitespace-nowrap">{toast.title}</b>{toast.body && <span className="text-muted-foreground hidden text-xs sm:block">{toast.body.slice(0, 90)}</span>}</div>}
          <div className="pointer-events-none absolute top-2 left-2 z-10 flex max-w-[64%] flex-col items-start gap-1.5 [&>*]:pointer-events-auto">
          {info && <div className="bg-background/85 flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs backdrop-blur" aria-live="polite">
            <span className={`size-2 shrink-0 rounded-full ${info.band === 0 ? "animate-pulse" : ""}`} style={{ background: TEAM_COLORS[info.teamIdx] }} />
            <span className="truncate font-medium">{info.text}</span>
            {info.band < 2 && <span className="text-muted-foreground shrink-0 text-[10px]">{info.band === 1 ? "likely" : "unsure"}</span>}
          </div>}
          {benchSel && !sel && <div className="bg-background/90 max-w-full rounded-xl border px-3 py-2 text-sm backdrop-blur">
            <b>{benchSel.name}</b> · {cfg.teams[codes[benchSel.team]].name}<div className="text-xs font-bold text-(--minute)">{benchSel.role}</div></div>}
          {sel && <div className="bg-background/90 max-w-full rounded-xl border px-3 py-2 text-sm backdrop-blur">
            <b>{sel.name}</b> · {sel.team}<div className="text-xs">{sel.role ? <><span className="font-bold text-(--minute)">{sel.role.role}</span> · averages {sel.role.x_in}% up the pitch in possession</> : "Role appears once the AI has read the shape."}</div></div>}
          </div>
        </div>
        <div className="hidden lg:block">{controls}</div>
      </div>

      <div className="min-w-0 px-3 pt-1.5 pb-[calc(24px+env(safe-area-inset-bottom))] lg:max-w-4xl lg:px-0 lg:pt-4">
        <div className="grid lg:hidden" style={{
          gridTemplateRows: hidePitch ? "0fr" : "1fr", opacity: hidePitch ? 0 : 1, visibility: hidePitch ? "hidden" : "visible",
          transition: hidePitch ? "grid-template-rows .5s ease, opacity .4s ease, visibility 0s linear .5s" : "grid-template-rows .5s ease, opacity .4s ease, visibility 0s",
        }}>
          <div className="min-h-0 overflow-hidden"><div className="pb-3">{controls}</div></div>
        </div>
        <Tabs defaultValue="moments">
          <div className="bg-background/85 backdrop-blur-md sticky top-(--hdr) z-20 -mx-3 px-3 pt-1 pb-2 lg:top-0 lg:mx-0 lg:px-0">
            <TabsList className="w-full"><TabsTrigger value="moments" onClick={() => setPitchHidden(true)}>Moments</TabsTrigger><TabsTrigger value="tactics" onClick={() => setPitchHidden(true)}>Tactics</TabsTrigger><TabsTrigger value="stats" onClick={() => setPitchHidden(true)}>Stats</TabsTrigger><TabsTrigger value="lineups" onClick={() => setPitchHidden(true)}>Line-ups</TabsTrigger></TabsList>
          </div>
          <TabsContent value="moments" className="space-y-2">
            {recap && <RecapCard recap={recap} codes={codes} />}
            {overlays.length === 0 && <p className="text-muted-foreground py-6 text-center text-sm">Waiting for the first key moment…</p>}
            <ol className="relative before:absolute before:top-2 before:bottom-0 before:left-[58px] before:w-px before:bg-border">
              {overlays.map((o) => <MomentCard key={o.moment_id} o={o} awayCode={codes[1]} />)}
            </ol>
            {overlays[0] && <details className="text-muted-foreground text-sm"><summary className="cursor-pointer">Machine-readable overlay (latest)</summary>
              <ScrollArea className="bg-muted mt-2 h-48 rounded-lg"><pre className="p-3 text-[11.5px]">{JSON.stringify(overlays[0], null, 2)}</pre></ScrollArea></details>}
          </TabsContent>
          <TabsContent value="tactics"><TacticsPanel tactics={tactics} codes={codes} selected={selected} onSelect={setSelected} /></TabsContent>
          <TabsContent value="stats"><StatsPanel stats={stats} codes={codes} /></TabsContent>
          <TabsContent value="lineups"><LineupsPanel cfg={cfg} codes={codes} tactics={tactics} subLog={subLog} cards={cards} goals={goals} /></TabsContent>
        </Tabs>
      </div>
      <Dialog open={momentumOpen} onOpenChange={setMomentumOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader><DialogTitle>Match momentum</DialogTitle><DialogDescription>Who was on top, minute by minute.</DialogDescription></DialogHeader>
          <MomentumChart series={series} goals={goals} cards={cards} codes={codes} names={codes.map((c) => cfg.teams[c].name)}
            score={[stats?.teams[codes[0]].goals ?? 0, stats?.teams[codes[1]].goals ?? 0]} minute={stats?.minute ?? 0} />
        </DialogContent>
      </Dialog>
      <SettingsSheet theme={themeMode} onTheme={setThemeMode} open={open} onOpenChange={setOpen} cfg={cfg} value={draft} onChange={setDraft} onApply={apply} />
    </div>
  )
}
