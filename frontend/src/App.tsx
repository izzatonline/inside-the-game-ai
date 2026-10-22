import { useEffect, useMemo, useRef, useState } from "react"
import { Activity, ArrowUpDown, Box, ChevronDown, ChevronRight, ChevronUp, Info, MapPin, Moon, PanelLeft, Pause, Play, RotateCcw, Settings as SettingsIcon, Sun } from "lucide-react"
import { MomentCard } from "@/components/MomentCard"
import { MomentumChart } from "@/components/MomentumChart"
import { RolesLegend } from "@/components/RolesLegend"
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
import { fmtMinute, shirtNo } from "@/lib/format"
import { useTheme } from "@/hooks/useTheme"
import { describeBall } from "@/lib/ball"
import { TEAM_COLORS, setTeamColors } from "@/lib/theme"
import type { BenchPick, Config, MatchInfo, Selected, Settings } from "@/lib/types"

const params = new URLSearchParams(location.search)
const initial: Settings = {
  match: params.get("match") ?? "", mode: params.get("mode") ?? "casual", lang: params.get("lang") ?? "en", team: params.get("team") ?? "", player: "",
  metric: params.get("metric") ?? "", src: params.get("src") ?? "stream", speed: params.get("speed") ?? "60", seed: params.get("seed") ?? "7", ai: params.get("ai") ?? "1",
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
    fetch(`/api/config?match=${matchId}`).then((r) => r.json()).then((c: Config) => { const t = Object.values(c.teams); setTeamColors(t[0].color, t[1].color); setCfg(c) })
  }, [matchId])
  if (!matches || !cfg) return <div className="space-y-3 p-4"><Skeleton className="h-14 w-full" /><Skeleton className="aspect-[105/77.5] w-full" /></div>
  return (
    <SidebarProvider>
      <AppSidebar matches={matches} matchId={matchId} onSelect={setMatchId} theme={theme.mode} onTheme={theme.setMode} />
      <SidebarInset className="bg-transparent">
        <Match key={matchId} cfg={cfg} matchId={matchId} theme={theme} next={matches.length > 1 ? matches[(matches.findIndex((m) => m.id === matchId) + 1) % matches.length] : null} onNext={() => setMatchId(matches[(matches.findIndex((m) => m.id === matchId) + 1) % matches.length].id)} />
      </SidebarInset>
    </SidebarProvider>
  )
}

function Match({ cfg, matchId, theme, next, onNext }: { cfg: Config; matchId: string; theme: ReturnType<typeof useTheme>; next: MatchInfo | null; onNext: () => void }) {
  const codes = Object.keys(cfg.teams)
  const [draft, setDraft] = useState(initial)
  const [applied, setApplied] = useState(initial)
  const [runId, setRunId] = useState(0)
  const [startMin, setStartMin] = useState(Number(params.get("start")) || 0)
  const [showEnd, setShowEnd] = useState(false)
  const [open, setOpen] = useState(false)
  const [layers, setLayers] = useState(["shape", "control", "roles", "offside"])
  const [focus, setFocus] = useState(window.innerWidth < 480 ? [codes[0]] : codes)
  const [selected, setSelected] = useState<Selected>(null)
  const [view3d, setView3d] = useState(params.get("view") !== "2d")
  const { frames, stats, tactics, overlays, recap, toast, ball, series, goals, cards, subLog, bench, roster, paused, pause } = useMatchStream({ ...applied, match: matchId }, runId, cfg, startMin)
  const { toggleSidebar } = useSidebar()
  const [benchSel, setBenchSel] = useState<BenchPick>(null)
  const info = ball ? describeBall(ball, cfg, codes) : null
  const narrow = useMemo(() => window.innerWidth < 480, [])
  const mobile = useIsMobile()
  const { mode: themeMode, setMode: setThemeMode, dark } = theme
  const [momentumOpen, setMomentumOpen] = useState(false)
  const [tab, setTab] = useState("moments")
  const [legendOpen, setLegendOpen] = useState(false)
  const [jump, setJump] = useState(0)
  const [hint, setHint] = useState(() => { try { return !localStorage.getItem("itg-hint-seen") } catch { return false } })
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
    setApplied(draft); setStartMin(0); setRunId((n) => n + 1); setOpen(false)
  }
  const sel = selected ? { sub: subLog.find((x) => x.team === codes[selected.team] && x.slot === selected.idx && x.player_in === (roster[codes[selected.team]] ?? [])[selected.idx]), name: (roster[codes[selected.team]] ?? cfg.teams[codes[selected.team]].players)[selected.idx], team: cfg.teams[codes[selected.team]].name, role: tactics[codes[selected.team]]?.roles[selected.idx] } : null
  const shape = codes.map((c, i) => ({ c, i, p: tactics[c] })).filter((x) => x.p)

  const nowMin = Math.floor((stats?.t ?? startMin * 60) / 60)
  const canJump = applied.src !== "live"
  const state: "playing" | "paused" | "ended" = recap ? "ended" : paused ? "paused" : "playing"
  const resumeFrom = (min: number) => { setStartMin(min); setRunId((n) => n + 1); setSelected(null); setBenchSel(null); setShowEnd(false) }
  const togglePlay = () => { if (state === "playing") pause(); else if (state === "paused") resumeFrom((stats?.t ?? 0) / 60); else resumeFrom(0) }
  const SPEEDS = ["30", "60", "120", "300"]
  const cycleSpeed = () => {
    const nextSpeed = SPEEDS[(SPEEDS.indexOf(applied.speed) + 1) % SPEEDS.length] ?? "60"
    setApplied({ ...applied, speed: nextSpeed }); setDraft((d) => ({ ...d, speed: nextSpeed }))
    resumeFrom(state === "ended" ? 0 : (stats?.t ?? 0) / 60)
  }
  useEffect(() => { if (recap) setShowEnd(true) }, [recap])
  const dismissHint = () => { setHint(false); try { localStorage.setItem("itg-hint-seen", "1") } catch { /* private mode */ } }
  const openTimeline = () => { setJump(nowMin); setMomentumOpen(true); dismissHint() }
  const doJump = (m: number) => { setStartMin(m); setRunId((n) => n + 1); setSelected(null); setBenchSel(null); setMomentumOpen(false) }
  useEffect(() => { if (!hint) return; const t = setTimeout(dismissHint, 9000); return () => clearTimeout(t) }, [hint])

  const controls = (
    <>
<div className="mt-2 flex max-w-full items-center gap-3 overflow-x-auto pb-1 [&>*]:shrink-0">
          <Button variant="outline" size="sm" onClick={cycleSpeed} aria-label="Change playback speed" title="Change playback speed" className="tabular-nums">{applied.speed}×</Button>
          <Toggle pressed={view3d} onPressedChange={setView3d} variant="outline" size="sm" aria-label="3D view"><Box /> 3D</Toggle>
          <ToggleGroup multiple value={layers} onValueChange={setLayers} variant="outline" size="sm" spacing={1}>
            <ToggleGroupItem value="shape">Team shape</ToggleGroupItem><ToggleGroupItem value="control">Territory</ToggleGroupItem>
            <ToggleGroupItem value="roles">Roles</ToggleGroupItem><ToggleGroupItem value="offside">Offside</ToggleGroupItem><ToggleGroupItem value="trail">Ball trail</ToggleGroupItem>
          </ToggleGroup>
          <ToggleGroup multiple value={focus} onValueChange={setFocus} variant="outline" size="sm" spacing={1}>
            {codes.map((c) => <ToggleGroupItem key={c} value={c}>{c}</ToggleGroupItem>)}
          </ToggleGroup>
          <Button variant="ghost" size="icon-sm" aria-label="What do the role badges mean?" title="What do the role badges mean?" onClick={() => setLegendOpen(true)}><Info /></Button>
        </div>
        <div className="text-muted-foreground mt-1.5 flex items-center gap-1.5 text-xs"><MapPin className="size-3 shrink-0" /><span className="truncate"><b className="text-foreground">{cfg.match.stadium}</b> · {cfg.teams[codes[0]].name} (home)</span></div>
        <div className="text-muted-foreground mt-1.5 flex flex-wrap gap-x-4 text-xs">
          {shape.map(({ c, i, p }) => <span key={c} className="flex items-center gap-1.5"><span className="size-2 rounded-full" style={{ background: TEAM_COLORS[i] }} /><b className="text-foreground">{p.formation}</b> {p.primary}</span>)}
        </div>
    </>
  )

  return (
    <div style={{ ["--pa" as string]: view3d ? 1.6 : 1.3548 }} className="grid grid-cols-[minmax(0,1fr)] lg:grid-cols-[min(calc(100%_-_440px),calc((100dvh_-_178px)_*_var(--pa)))_minmax(0,1fr)] lg:gap-6 lg:px-5">
      <div ref={headerRef} className="bg-background/85 sticky top-0 z-30 min-w-0 border-b backdrop-blur-md px-3 pt-[calc(8px+env(safe-area-inset-top))] pb-1.5 lg:self-start lg:px-0 lg:pt-4">
        <div className="relative">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-lg" aria-label="Matches menu" onClick={toggleSidebar}><PanelLeft /></Button>
          <Card size="sm" className="hover:bg-muted/40 min-w-0 flex-1 cursor-pointer transition-colors" role="button" tabIndex={0} aria-label="Show match momentum" onClick={openTimeline} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") openTimeline() }}>
              <CardContent className="grid grid-cols-[1fr_auto_1fr] items-center px-2 sm:px-4">
            <div className="flex min-w-0 items-center gap-1.5 text-sm font-semibold max-[359px]:text-xs"><span className="size-2.5 shrink-0 rounded-full max-[359px]:hidden" style={{ background: TEAM_COLORS[0] }} /><span className="truncate">{narrow ? codes[0] : cfg.teams[codes[0]].name}</span></div>
            <div className="px-1.5 text-center sm:px-3"><div className="text-xl leading-none font-extrabold tabular-nums min-[360px]:text-2xl">{stats?.teams[codes[0]].goals ?? 0}-{stats?.teams[codes[1]].goals ?? 0}</div><div className="flex items-center justify-center gap-1 text-[11px] font-bold text-(--minute)">{fmtMinute(stats?.minute ?? 0)}'<Activity className="text-muted-foreground size-3 max-[359px]:hidden" /></div></div>
            <div className="flex min-w-0 items-center justify-end gap-1.5 text-sm font-semibold max-[359px]:text-xs"><span className="truncate">{narrow ? codes[1] : cfg.teams[codes[1]].name}</span><span className="size-2.5 shrink-0 rounded-full max-[359px]:hidden" style={{ background: TEAM_COLORS[1] }} /></div>
          </CardContent>
            </Card>
          <Button variant={state === "ended" ? "default" : "outline"} size="icon-lg" aria-label={state === "playing" ? "Pause match" : state === "paused" ? "Resume match" : "Replay match"} title={state === "playing" ? "Pause" : state === "paused" ? "Resume" : "Replay from kick-off"} onClick={togglePlay}>{state === "playing" ? <Pause /> : state === "paused" ? <Play /> : <RotateCcw />}</Button>
          {mobile && <Button variant="outline" size="icon-lg" aria-label={pitchHidden ? "Show pitch" : "Hide pitch"} aria-expanded={!pitchHidden} onClick={() => setPitchHidden((h) => !h)}>{pitchHidden ? <ChevronDown /> : <ChevronUp />}</Button>}
          <Button variant="outline" size="icon-lg" aria-label="Toggle light or dark mode" className="hidden sm:inline-flex" onClick={() => setThemeMode(dark ? "light" : "dark")}>{dark ? <Sun /> : <Moon />}</Button>
          <Button variant="outline" size="icon-lg" aria-label="Settings" onClick={() => setOpen(true)}><SettingsIcon /></Button>
        </div>
        <div className="my-2">
          <div className="h-1 overflow-hidden rounded" style={{ background: TEAM_COLORS[1] }}><div className="h-full transition-all duration-500" style={{ background: TEAM_COLORS[0], width: `${50 + 50 * (stats?.momentum ?? 0)}%` }} /></div>
        </div>
        {hint && canJump && (
          <button onClick={dismissHint} className="bg-foreground text-background animate-in fade-in slide-in-from-top-1 absolute top-full left-1/2 z-40 mt-0.5 -translate-x-1/2 rounded-full px-3 py-1 text-[11px] font-medium whitespace-nowrap shadow-lg">
            Tip: tap the score to jump to any minute ✕
          </button>
        )}
      </div>
        <div ref={pitchBox} className="border-border relative overflow-hidden rounded-2xl border shadow-2xl will-change-[opacity,max-height]"
          style={mobile && pitchH ? {
            opacity: hidePitch ? 0 : 1, maxHeight: hidePitch ? 0 : pitchH, visibility: hidePitch ? "hidden" : "visible",
            transition: hidePitch ? "max-height .5s ease, opacity .4s ease, visibility 0s linear .5s" : "max-height .5s ease, opacity .4s ease, visibility 0s",
          } : undefined}>
          <PitchCanvas frames={frames} tactics={tactics} codes={codes} names={codes.map((c) => roster[c] ?? cfg.teams[c].players)} nums={codes.map((c) => (roster[c] ?? cfg.teams[c].players).map((nm, i) => shirtNo(cfg, c, nm) ?? cfg.teams[c].numbers[i]))} staff={codes.map((c) => cfg.teams[c].staff)} bench={bench} onBench={setBenchSel} benchSel={benchSel} layers={layers} focus={focus} selected={selected} onSelect={(x) => { setSelected(x); if (x) setBenchSel(null) }} view3d={view3d} />
          <Badge variant="secondary" className="absolute top-2 right-2 hidden sm:inline-flex">{state === "ended" ? "Full time" : state === "paused" ? "Paused" : `Playing · ${applied.speed}×`}</Badge>
          {view3d && <Badge variant="outline" className="bg-background/70 absolute top-2 right-2 text-[10px] backdrop-blur sm:top-9">Drag to rotate · double-tap to reset</Badge>}
          {toast && <div key={toast.id} className={`bg-background/90 animate-in fade-in slide-in-from-top-2 absolute top-2 left-1/2 max-w-[90%] -translate-x-1/2 rounded-xl border px-3 py-1.5 text-center backdrop-blur ${toast.goal ? "border-emerald-400" : ""}`}>
            <b className="block text-sm whitespace-nowrap">{toast.title}</b>{toast.body && <span className="text-muted-foreground hidden text-xs sm:block">{toast.body.slice(0, 90)}</span>}</div>}
          {recap && showEnd && (
            <div className="bg-background/55 absolute inset-0 z-20 grid place-items-center backdrop-blur-[2px]">
              <div className="bg-background/95 w-[min(88%,22rem)] space-y-3 rounded-2xl border p-4 text-center shadow-xl">
                <div className="text-muted-foreground text-[11px] font-semibold tracking-[0.2em] uppercase">Full time</div>
                <div className="text-3xl font-black tabular-nums">{stats?.teams[codes[0]].goals ?? 0} - {stats?.teams[codes[1]].goals ?? 0}</div>
                <div className="grid gap-2">
                  <Button onClick={() => resumeFrom(0)}><RotateCcw /> Replay match</Button>
                  {next && <Button variant="outline" onClick={onNext}>Next: {next.title} <ChevronRight /></Button>}
                  <Button variant="ghost" onClick={() => { setTab("stats"); setPitchHidden(true); setShowEnd(false) }}>See the match report</Button>
                </div>
                <button className="text-muted-foreground text-xs underline" onClick={() => setShowEnd(false)}>Close and look at the pitch</button>
              </div>
            </div>
          )}
          <div className="pointer-events-none absolute top-2 left-2 z-10 flex max-w-[64%] flex-col items-start gap-1.5 [&>*]:pointer-events-auto">
          {info && <div className="bg-background/85 flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs backdrop-blur" aria-live="polite">
            <span className={`size-2 shrink-0 rounded-full ${info.band === 0 ? "animate-pulse" : ""}`} style={{ background: TEAM_COLORS[info.teamIdx] }} />
            <span className="truncate font-medium">{info.text}</span>
            {info.band < 2 && <span className="text-muted-foreground shrink-0 text-[10px]">{info.band === 1 ? "likely" : "unsure"}</span>}
          </div>}
          {benchSel && !sel && <div className="bg-background/90 max-w-full rounded-xl border px-3 py-2 text-sm backdrop-blur">
            <b>{benchSel.name}</b> · {cfg.teams[codes[benchSel.team]].name}<div className="text-xs font-bold text-(--minute)">{benchSel.role}</div></div>}
          {sel && <div className="bg-background/90 max-w-full rounded-xl border px-3 py-2 text-sm backdrop-blur">
            <b>{sel.name}</b> · {sel.team}{sel.sub && <span className="ml-1.5 inline-flex items-center gap-0.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400"><ArrowUpDown className="size-3" />sub {fmtMinute(sel.sub.minute)}'</span>}<div className="text-xs">{sel.role ? <><span className="font-bold text-(--minute)">{sel.role.role}</span> · averages {sel.role.x_in}% up the pitch in possession</> : "Role appears once the AI has read the shape."}</div></div>}
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
        <Tabs value={tab} onValueChange={(v) => setTab(v as string)}>
          <div className="bg-background/85 backdrop-blur-md sticky top-(--hdr) z-20 -mx-3 px-3 pt-1 pb-2 lg:top-0 lg:mx-0 lg:px-0">
            <TabsList className="w-full"><TabsTrigger value="moments" onClick={() => setPitchHidden(true)}>Moments</TabsTrigger><TabsTrigger value="tactics" onClick={() => setPitchHidden(true)}>Tactics</TabsTrigger><TabsTrigger value="stats" onClick={() => setPitchHidden(true)}>Stats</TabsTrigger><TabsTrigger value="lineups" onClick={() => setPitchHidden(true)}>Line-ups</TabsTrigger></TabsList>
          </div>
          <TabsContent value="moments" className="space-y-2">
            {recap && <RecapCard recap={recap} codes={codes} onReport={() => { setTab("stats"); setPitchHidden(true) }} />}
            {overlays.length === 0 && <p className="text-muted-foreground py-6 text-center text-sm">Waiting for the first key moment…</p>}
            <ol className="relative before:absolute before:top-2 before:bottom-0 before:left-[58px] before:w-px before:bg-border">
              {overlays.map((o) => <MomentCard key={o.moment_id} o={o} awayCode={codes[1]} />)}
            </ol>
            {overlays[0] && <details className="text-muted-foreground text-sm"><summary className="cursor-pointer">Machine-readable overlay (latest)</summary>
              <ScrollArea className="bg-muted mt-2 h-48 rounded-lg"><pre className="p-3 text-[11.5px]">{JSON.stringify(overlays[0], null, 2)}</pre></ScrollArea></details>}
          </TabsContent>
          <TabsContent value="tactics"><TacticsPanel tactics={tactics} codes={codes} selected={selected} onSelect={setSelected} subLog={subLog} /></TabsContent>
          <TabsContent value="stats"><StatsPanel cfg={cfg} stats={stats} codes={codes} recap={recap} /></TabsContent>
          <TabsContent value="lineups"><LineupsPanel stats={stats} cfg={cfg} codes={codes} subLog={subLog} cards={cards} goals={goals} /></TabsContent>
        </Tabs>
      </div>
      <Dialog open={momentumOpen} onOpenChange={setMomentumOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Match timeline</DialogTitle>
            <DialogDescription>{canJump ? "See who was on top minute by minute, then jump to any moment." : "Who was on top, minute by minute. Jumping is only available in replay mode."}</DialogDescription>
          </DialogHeader>
          <MomentumChart series={series} goals={goals} cards={cards} codes={codes} names={codes.map((c) => cfg.teams[c].name)}
            score={[stats?.teams[codes[0]].goals ?? 0, stats?.teams[codes[1]].goals ?? 0]} minute={stats?.minute ?? 0}
            max={cfg.match.duration_min} playhead={canJump ? jump : null} onPick={canJump ? setJump : undefined} />
          {canJump && (
            <div className="space-y-2.5">
              {goals.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-muted-foreground text-xs">Jump to a goal:</span>
                  {goals.map((g, i) => (
                    <button key={i} onClick={() => setJump(Math.max(0, g.minute - 1))} className="bg-muted hover:bg-muted/70 rounded-full px-2.5 py-1 text-xs">⚽ {fmtMinute(g.minute)}' {g.player ? g.player.split(" ").slice(-1)[0] : ""}</button>
                  ))}
                </div>
              )}
              <Button className="w-full" onClick={() => doJump(jump)}>Jump to {fmtMinute(jump)}'</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
      <RolesLegend open={legendOpen} onOpenChange={setLegendOpen} />
      <SettingsSheet theme={themeMode} onTheme={setThemeMode} open={open} onOpenChange={setOpen} cfg={cfg} value={draft} onChange={setDraft} onApply={apply} />
    </div>
  )
}
