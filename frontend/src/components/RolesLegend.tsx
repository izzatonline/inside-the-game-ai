import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { BADGE_COLORS } from "@/lib/theme"

const ROLES: [string, string, string][] = [
  ["GK", "Goalkeeper", "Last line of defence."],
  ["CB", "Centre-back", "Central defender."],
  ["FB", "Full-back", "Wide defender who stays on the flank."],
  ["IFB", "Inverted full-back", "Steps into midfield when his team has the ball."],
  ["OFB", "Overlapping full-back", "Runs beyond the winger to attack."],
  ["DM", "Holding midfielder", "Sits in front of the defence and screens it."],
  ["B2B", "Box-to-box midfielder", "Covers ground in both penalty areas."],
  ["A8", "Advanced 8", "Central midfielder who pushes up to join attacks."],
  ["CAM", "Number 10", "Attacking midfielder playing behind the striker."],
  ["W", "Winger", "Stays wide and attacks down the touchline."],
  ["IW", "Inverted winger", "Starts wide, then cuts inside."],
  ["IF", "Inside forward", "Forward who drifts inside from the flank."],
  ["ST", "Striker", "Main central attacker."],
]

export function RolesLegend({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>What the role badges mean</DialogTitle>
          <DialogDescription>The AI infers each player's role from where he actually stands with and without the ball. Roles are not assigned by hand, and the number inside each circle is the shirt number.</DialogDescription>
        </DialogHeader>
        <ul className="grid gap-2">
          {ROLES.map(([code, name, text]) => (
            <li key={code} className="grid grid-cols-[3rem_1fr] items-center gap-3 text-sm">
              <span className="rounded-md px-1.5 py-0.5 text-center text-[11px] font-extrabold text-black" style={{ background: BADGE_COLORS[code] }}>{code}</span>
              <span><b>{name}</b> <span className="text-muted-foreground">{text}</span></span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
