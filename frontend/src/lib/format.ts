import type { Config } from "@/lib/types"
/** Stoppage time reads 90+3', not 93'. */
export const fmtMinute = (m: number) => (m > 90 ? `90+${m - 90}` : String(m))

/** Shirt number for a player on a given side: starters are listed in `numbers`, substitutes carry theirs. */
export function shirtNo(cfg: Config, code: string, name: string): number | null {
  const t = cfg.teams[code]
  const i = t.players.indexOf(name)
  if (i >= 0) return t.numbers[i]
  return t.staff.subs.find((s) => s.name === name)?.number ?? null
}
