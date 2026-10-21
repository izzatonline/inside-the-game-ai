import { useEffect, useState } from "react"
import { Moon, Sparkles, Sun, SunMoon } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { ThemeMode } from "@/hooks/useTheme"
import type { Config, Settings } from "@/lib/types"

type Props = {
  theme: ThemeMode; onTheme: (m: ThemeMode) => void; open: boolean; onOpenChange: (o: boolean) => void
  cfg: Config; value: Settings; onChange: (s: Settings) => void; onApply: () => void
}
type Item = { value: string; label: string; icon?: React.ReactNode }

const NARRATION: Record<string, string> = { foundry: "Narrated by Microsoft Foundry", "azure-openai": "Narrated by Azure OpenAI", offline: "Narrated by built-in rules" }

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-muted-foreground text-[11px] font-semibold tracking-[0.12em] uppercase">{title}</h3>
      <div className="space-y-4">{children}</div>
    </section>
  )
}

function Row({ label, help, children, htmlFor }: { label: string; help?: string; children: React.ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor} className="text-sm font-medium">{label}</Label>
      {children}
      {help && <p className="text-muted-foreground text-xs leading-snug">{help}</p>}
    </div>
  )
}

function Segment({ value, items, onValue, label }: { value: string; items: Item[]; onValue: (v: string) => void; label: string }) {
  return (
    <ToggleGroup value={[value]} onValueChange={(v) => { if (v[0] !== undefined) onValue(v[0]) }} variant="outline" spacing={0} className="w-full" aria-label={label}>
      {items.map((i) => <ToggleGroupItem key={i.value} value={i.value} className="flex-1 gap-1.5">{i.icon}{i.label}</ToggleGroupItem>)}
    </ToggleGroup>
  )
}

function Choose({ id, value, items, onValue }: { id: string; value: string; items: Item[]; onValue: (v: string) => void }) {
  return (
    <Select value={value} onValueChange={(v) => onValue(v ?? "")} items={items}>
      <SelectTrigger id={id} className="w-full"><SelectValue /></SelectTrigger>
      <SelectContent>{items.map((i) => <SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>)}</SelectContent>
    </Select>
  )
}

export function SettingsSheet({ theme, onTheme, open, onOpenChange, cfg, value, onChange, onApply }: Props) {
  const [wide, setWide] = useState(() => window.matchMedia("(min-width: 640px)").matches)
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 640px)")
    const on = () => setWide(mq.matches)
    mq.addEventListener("change", on)
    return () => mq.removeEventListener("change", on)
  }, [])
  const set = (k: keyof Settings) => (v: string) => onChange({ ...value, [k]: v })
  const codes = Object.keys(cfg.teams)
  const players = codes.flatMap((c) => cfg.teams[c].players.map((p, i) => ({ value: `${c}:${i}:${p}`, label: `${p} (${c})` })))
  const live = value.src === "live"
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={wide ? "right" : "bottom"}
        className="gap-0 p-0 max-sm:mx-2 max-sm:mb-[max(0.5rem,env(safe-area-inset-bottom))] max-sm:max-h-[88dvh] max-sm:rounded-3xl max-sm:border sm:w-[26rem] sm:max-w-none"
      >
        <SheetHeader className="space-y-1.5 px-5 pt-5 pb-3">
          <SheetTitle className="text-lg">Customise</SheetTitle>
          <SheetDescription>Tailor how this match is told to you.</SheetDescription>
          <Badge variant="secondary" className="w-fit gap-1.5"><Sparkles className="size-3" />{NARRATION[cfg.llm] ?? `Narrated by ${cfg.llm}`}</Badge>
        </SheetHeader>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 pt-1 pb-5">
          <Section title="Appearance">
            <Segment label="Appearance" value={theme} onValue={(v) => onTheme(v as ThemeMode)} items={[
              { value: "system", label: "Auto", icon: <SunMoon className="size-3.5" /> },
              { value: "light", label: "Light", icon: <Sun className="size-3.5" /> },
              { value: "dark", label: "Dark", icon: <Moon className="size-3.5" /> },
            ]} />
          </Section>

          <Section title="How you watch">
            <Row label="AI narration" help={cfg.llm === "offline" ? "No AI model is connected, so wording always comes from templates." : value.ai === "0" ? "Fixed template wording only. Faster and free." : `Wording is written by an AI model and fact-checked. Tap the label on any card to see how.`}>
              <Segment label="AI narration" value={value.ai} onValue={set("ai")} items={[{ value: "1", label: "On", icon: <Sparkles className="size-3.5" /> }, { value: "0", label: "Off" }]} />
            </Row>
            <Row label="Style" help={value.mode === "analyst" ? "Adds the numbers, the 'why' behind each moment and tactical detail." : "Plain-language highlights without the number crunching."}>
              <Segment label="Style" value={value.mode} onValue={set("mode")} items={[{ value: "casual", label: "Casual fan" }, { value: "analyst", label: "Analyst" }]} />
            </Row>
            <Row label="Language" htmlFor="lang">
              <Choose id="lang" value={value.lang} onValue={set("lang")} items={Object.entries(cfg.languages).map(([v, label]) => ({ value: v, label }))} />
            </Row>
            <Row label="Favourite club" htmlFor="team" help="Shows your club's moments, plus every goal.">
              <Choose id="team" value={value.team} onValue={set("team")} items={[{ value: "", label: "No favourite" }, ...codes.map((c) => ({ value: c, label: cfg.teams[c].name }))]} />
            </Row>
            <Row label="Follow a player" htmlFor="player" help="Only their moments, plus goals.">
              <Choose id="player" value={value.player} onValue={set("player")} items={[{ value: "", label: "Nobody" }, ...players]} />
            </Row>
            <Row label="Focus on one stat">
              <Segment label="Focus on one stat" value={value.metric} onValue={set("metric")} items={[
                { value: "", label: "All" }, { value: "xg", label: "xG" }, { value: "speed", label: "Speed" }, { value: "passing", label: "Passing" },
              ]} />
            </Row>
          </Section>

          <Section title="Replay">
            <Row label="Speed" help={`${value.speed}× plays a 90-minute match in about ${Math.max(1, Math.round(5400 / Number(value.speed || 60)))} seconds.`}>
              <Segment label="Speed" value={value.speed} onValue={set("speed")} items={["30", "60", "120", "300"].map((v) => ({ value: v, label: `${v}×` }))} />
            </Row>
            <Row label="Feed" help={live ? "Shared live feed for many viewers. Jumping to a minute needs Replay." : "Your own replay. You can jump to any minute."}>
              <Segment label="Feed" value={value.src} onValue={set("src")} items={[{ value: "stream", label: "Replay" }, { value: "live", label: "Live feed" }]} />
            </Row>
            <details className="group rounded-lg border px-3 py-2 text-sm">
              <summary className="text-muted-foreground cursor-pointer select-none">Advanced</summary>
              <div className="mt-3">
                <Row label="Match seed" htmlFor="seed" help="The same seed always gives the same match.">
                  <Input id="seed" type="number" value={value.seed} onChange={(e) => set("seed")(e.target.value)} />
                </Row>
              </div>
            </details>
          </Section>
        </div>

        <div className="bg-popover border-t px-5 pt-3 pb-[calc(1rem+env(safe-area-inset-bottom))] max-sm:rounded-b-3xl max-sm:pb-4">
          <Button size="lg" className="w-full" onClick={onApply}>Apply and restart match</Button>
          <p className="text-muted-foreground mt-2 text-center text-[11px]">Appearance changes apply instantly. Other changes restart from kick-off.</p>
        </div>
      </SheetContent>
    </Sheet>
  )
}
