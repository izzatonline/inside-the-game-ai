import { Check, Cpu, ScanSearch, Sparkles, TriangleAlert } from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import type { Overlay } from "@/lib/types"

const HOW: Record<string, string> = {
  ai: "Written by an AI model, then fact-checked.",
  fallback: "The AI's wording was unavailable or failed the check, so fixed template wording was used instead.",
  ai_off: "AI narration is switched off in Settings, so this is fixed template wording filled with the match facts.",
  rules: "No AI model is connected, so this is fixed template wording filled with the match facts.",
}

const human = (k: string) => k.replace(/_/g, " ").replace(/\b(xg|ppda)\b/i, (m) => m.toUpperCase())
const flat = (f: Record<string, unknown>) =>
  Object.entries(f).filter(([k, v]) => v !== null && v !== "" && typeof v !== "object" && !["team", "id"].includes(k)).slice(0, 14)

function Step({ icon, title, who, children }: { icon: React.ReactNode; title: string; who: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="bg-muted mt-0.5 grid size-8 shrink-0 place-items-center rounded-full">{icon}</span>
      <div className="min-w-0 text-sm">
        <p className="font-semibold">{title} <span className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">· {who}</span></p>
        <div className="text-muted-foreground text-[13px] leading-snug">{children}</div>
      </div>
    </li>
  )
}

/** Explains one card: who detected the moment, who wrote the words, and what the fact-checker verified. */
export function ProvenanceDialog({ o, open, onOpenChange }: { o: Overlay; open: boolean; onOpenChange: (v: boolean) => void }) {
  const c = o.check
  const ai = c?.how === "ai"
  const facts = flat(o.facts ?? {})
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>How this was made</DialogTitle>
          <DialogDescription>{HOW[c?.how ?? "rules"]}</DialogDescription>
        </DialogHeader>
        <ol className="space-y-4">
          <Step icon={<ScanSearch className="size-4" />} title="Spotted the moment" who="rules, not AI">
            Code watched the event stream and calculated every number below (xG, pressure, speed…). No AI is involved in the maths.
          </Step>
          <Step icon={<Sparkles className="size-4" />} title="Wrote the words" who={ai ? `AI · ${o.model}` : "template"}>
            {ai ? "Given only the facts below and told never to invent numbers, names or events." : "A fixed sentence with the facts filled in."}
          </Step>
          <Step icon={<Cpu className="size-4" />} title="Fact-check" who="rules, not AI">
            {ai ? (
              c.unmatched?.length ? <span className="text-destructive flex items-center gap-1"><TriangleAlert className="size-3.5" />Found numbers not in the facts ({c.unmatched.join(", ")}).</span>
              : <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400"><Check className="size-3.5" />{c.matched} of {c.numbers} numbers in the text were found in the facts.</span>
            ) : "Nothing to check: template wording is written ahead of time."}
            {" "}It checks numbers only; it does not judge football rules or opinions.
          </Step>
        </ol>
        {facts.length > 0 && (
          <section>
            <h4 className="text-muted-foreground mb-2 text-[11px] font-semibold tracking-[0.12em] uppercase">Facts it was given</h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[13px]">
              {facts.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2 border-b pb-1"><dt className="text-muted-foreground capitalize">{human(k)}</dt><dd className="font-semibold tabular-nums">{String(v)}</dd></div>
              ))}
            </dl>
          </section>
        )}
      </DialogContent>
    </Dialog>
  )
}
