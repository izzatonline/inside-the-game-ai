import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import type { ThemeMode } from "@/hooks/useTheme"
import type { Config, Settings } from "@/lib/types"

type Props = { theme: ThemeMode; onTheme: (m: ThemeMode) => void; open: boolean; onOpenChange: (o: boolean) => void; cfg: Config; value: Settings; onChange: (s: Settings) => void; onApply: () => void }

function Field({ id, label, value, items, onValue }: { id: string; label: string; value: string; items: { value: string; label: string }[]; onValue: (v: string) => void }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value} onValueChange={(v) => onValue(v ?? "")} items={items}>
        <SelectTrigger id={id} className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent>{items.map((i) => <SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>)}</SelectContent>
      </Select>
    </div>
  )
}

export function SettingsSheet({ theme, onTheme, open, onOpenChange, cfg, value, onChange, onApply }: Props) {
  const set = (k: keyof Settings) => (v: string) => onChange({ ...value, [k]: v })
  const codes = Object.keys(cfg.teams)
  const players = codes.flatMap((c) => cfg.teams[c].players.map((p, i) => ({ value: `${c}:${i}:${p}`, label: `${p} (${c})` })))
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="max-h-[92dvh] overflow-y-auto sm:mx-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Make it yours</SheetTitle>
          <SheetDescription>The same match, tailored to the viewer. Model: {cfg.llm} · orchestration: {cfg.orchestration}.</SheetDescription>
        </SheetHeader>
        <div className="grid gap-3 px-4 pb-4">
          <Field id="theme" label="Appearance" value={theme} onValue={(v) => onTheme(v as ThemeMode)} items={[{ value: "system", label: "Match my device" }, { value: "light", label: "Day (light)" }, { value: "dark", label: "Night (dark)" }]} />
          <Field id="mode" label="View" value={value.mode} onValue={set("mode")} items={[{ value: "casual", label: "Casual fan" }, { value: "analyst", label: "Analyst" }]} />
          <Field id="lang" label="Language" value={value.lang} onValue={set("lang")} items={Object.entries(cfg.languages).map(([v, label]) => ({ value: v, label }))} />
          <Field id="team" label="Favourite club" value={value.team} onValue={set("team")} items={[{ value: "", label: "Neutral" }, ...codes.map((c) => ({ value: c, label: cfg.teams[c].name }))]} />
          <Field id="player" label="Player focus" value={value.player} onValue={set("player")} items={[{ value: "", label: "None" }, ...players]} />
          <Field id="metric" label="Single metric" value={value.metric} onValue={set("metric")} items={[{ value: "", label: "All" }, { value: "xg", label: "xG" }, { value: "speed", label: "Speed" }, { value: "passing", label: "Passing" }]} />
          <Field id="src" label="Source" value={value.src} onValue={set("src")} items={[{ value: "stream", label: "Replay" }, { value: "live", label: "Live bus" }]} />
          <Field id="speed" label="Speed" value={value.speed} onValue={set("speed")} items={["30", "60", "120", "300"].map((v) => ({ value: v, label: `${v}×` }))} />
          <div className="space-y-1.5"><Label htmlFor="seed">Seed</Label><Input id="seed" type="number" value={value.seed} onChange={(e) => set("seed")(e.target.value)} /></div>
          <Button size="lg" onClick={onApply}>Kick off</Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
