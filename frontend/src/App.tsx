import { useEffect, useMemo, useState } from "react"
import { Box, Settings2 } from "lucide-react"
import { MomentCard } from "@/components/MomentCard"
import { PitchCanvas } from "@/components/PitchCanvas"
import { SettingsSheet } from "@/components/SettingsSheet"
import { StatsPanel } from "@/components/StatsPanel"
import { TacticsPanel } from "@/components/TacticsPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Toggle } from "@/components/ui/toggle"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useMatchStream } from "@/hooks/useMatchStream"
import { TEAM_COLORS } from "@/lib/theme"
import type { Config, Selected, Settings } from "@/lib/types"

const params = new URLSearchParams(location.search)
const initial: Settings = {
  mode: params.get("mode") ?? "casual", lang: params.get("lang") ?? "en", team: params.get("team") ?? "", player: "",
  metric: params.get("metric") ?? "", src: params.get("src") ?? "stream", speed: params.get("speed") ?? "60", seed: params.get("seed") ?? "7",
}

export default function App() {
  const [cfg, setCfg] = useState<Config | null>(null)
  useEffect(() => { fetch("/api/config").then((r) => r.json()).then(setCfg) }, [])
  if (!cfg) return <div className="space-y-3 p-4"><Skeleton className="h-14 w-full" /><Skeleton className="aspect-[105/68] w-full" /></div>
  return <Match cfg={cfg} />
}

function Match({ cfg }: { cfg: Config }) {
  const codes = Object.keys(cfg.teams)
  const [draft, setDraft] = useState(initial)
  const [applied, setApplied] = useState(initial)
  const [runId, setRunId] = useState(0)
  const [open, setOpen] = useState(false)
  const [layers, setLayers] = useState(["shape", "control", "roles", "trail"])
  const [focus, setFocus] = useState(window.innerWidth < 480 ? [codes[0]] : codes)
  const [selected, setSelected] = useState<Selected>(null)
  const [view3d, setView3d] = useState(params.get("view") === "3d")
  const { frames, stats, tactics, overlays, recap, status, toast } = useMatchStream(applied, runId)
  const narrow = useMemo(() => window.innerWidth < 480, [])

  const apply = () => {
    const [c, i] = draft.player ? draft.player.split(":") : []
    setSelected(c ? { team: codes.indexOf(c), idx: Number(i) } : null)
    setApplied(draft); setRunId((n) => n + 1); setOpen(false)
  }
  const sel = selected ? { name: cfg.teams[codes[selected.team]].players[selected.idx], team: cfg.teams[codes[selected.team]].name, role: tactics[codes[selected.team]]?.roles[selected.idx] } : null
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
    <div className="mx-auto grid max-w-[1180px] grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,1.55fr)_minmax(340px,1fr)] lg:gap-4 lg:px-4">
      <div className="bg-background sticky top-0 z-10 min-w-0 border-b px-3 pt-[calc(8px+env(safe-area-inset-top))] pb-1.5 lg:self-start lg:px-0 lg:pt-4">
        <div className="flex items-center gap-2">
          <Card size="sm" className="flex-1"><CardContent className="grid grid-cols-[1fr_auto_1fr] items-center">
            <div className="flex min-w-0 items-center gap-2 text-sm font-semibold"><span className="size-2.5 shrink-0 rounded-full" style={{ background: TEAM_COLORS[0] }} /><span className="truncate">{narrow ? codes[0] : cfg.teams[codes[0]].name}</span></div>
            <div className="px-3 text-center"><div className="text-2xl leading-none font-extrabold tabular-nums">{stats?.teams[codes[0]].goals ?? 0}-{stats?.teams[codes[1]].goals ?? 0}</div><div className="text-[11px] font-bold text-amber-400">{stats?.minute ?? 0}'</div></div>
            <div className="flex min-w-0 items-center justify-end gap-2 text-sm font-semibold"><span className="truncate">{narrow ? codes[1] : cfg.teams[codes[1]].name}</span><span className="size-2.5 shrink-0 rounded-full" style={{ background: TEAM_COLORS[1] }} /></div>
          </CardContent></Card>
          <Button variant="outline" size="icon-lg" aria-label="Settings" onClick={() => setOpen(true)}><Settings2 /></Button>
        </div>
        <div className="my-2 h-1 overflow-hidden rounded bg-rose-500"><div className="h-full bg-sky-400 transition-all duration-500" style={{ width: `${50 + 50 * (stats?.momentum ?? 0)}%` }} /></div>
        <div className="border-border relative overflow-hidden rounded-2xl border shadow-2xl">
          <PitchCanvas frames={frames} tactics={tactics} codes={codes} layers={layers} focus={focus} selected={selected} onSelect={setSelected} view3d={view3d} />
          <Badge variant="secondary" className="absolute top-2 left-2 hidden sm:inline-flex">{status}</Badge>
          {view3d && <Badge variant="outline" className="bg-background/70 absolute right-2 bottom-2 text-[10px] backdrop-blur">Drag to rotate · double-tap to reset</Badge>}
          {toast && <div key={toast.id} className={`bg-background/90 animate-in fade-in slide-in-from-top-2 absolute top-2 left-1/2 max-w-[90%] -translate-x-1/2 rounded-xl border px-3 py-1.5 text-center backdrop-blur ${toast.goal ? "border-emerald-400" : ""}`}>
            <b className="block text-sm whitespace-nowrap">{toast.title}</b>{toast.body && <span className="text-muted-foreground hidden text-xs sm:block">{toast.body.slice(0, 90)}</span>}</div>}
          {sel && <div className="bg-background/90 absolute inset-x-2 bottom-2 rounded-xl border px-3 py-2 text-sm backdrop-blur">
            <b>{sel.name}</b> · {sel.team}<div className="text-xs">{sel.role ? <><span className="font-bold text-amber-400">{sel.role.role}</span> · averages {sel.role.x_in}% up the pitch in possession</> : "Role appears once the AI has read the shape."}</div></div>}
        </div>
        <div className="hidden lg:block">{controls}</div>
      </div>

      <div className="min-w-0 px-3 pt-1.5 pb-[calc(24px+env(safe-area-inset-bottom))] lg:px-0 lg:pt-4">
        <div className="mb-3 lg:hidden">{controls}</div>
        <Tabs defaultValue="moments">
          <TabsList className="w-full"><TabsTrigger value="moments">Moments</TabsTrigger><TabsTrigger value="tactics">Tactics</TabsTrigger><TabsTrigger value="stats">Stats</TabsTrigger></TabsList>
          <TabsContent value="moments" className="space-y-2">
            {recap && <Card size="sm" className="bg-emerald-500/10"><CardContent><h3 className="font-semibold">{recap.headline}</h3><p className="text-sm">{recap.body}</p><span className="text-muted-foreground text-[11px]">{recap.source === "llm" ? "AI-written recap" : "rules-based recap"}</span></CardContent></Card>}
            {overlays.length === 0 && <p className="text-muted-foreground py-6 text-center text-sm">Waiting for the first key moment…</p>}
            {overlays.map((o) => <MomentCard key={o.moment_id} o={o} awayCode={codes[1]} />)}
            {overlays[0] && <details className="text-muted-foreground text-sm"><summary className="cursor-pointer">Machine-readable overlay (latest)</summary>
              <ScrollArea className="bg-muted mt-2 h-48 rounded-lg"><pre className="p-3 text-[11.5px]">{JSON.stringify(overlays[0], null, 2)}</pre></ScrollArea></details>}
          </TabsContent>
          <TabsContent value="tactics"><TacticsPanel tactics={tactics} codes={codes} selected={selected} onSelect={setSelected} /></TabsContent>
          <TabsContent value="stats"><StatsPanel stats={stats} codes={codes} /></TabsContent>
        </Tabs>
      </div>
      <SettingsSheet open={open} onOpenChange={setOpen} cfg={cfg} value={draft} onChange={setDraft} onApply={apply} />
    </div>
  )
}
