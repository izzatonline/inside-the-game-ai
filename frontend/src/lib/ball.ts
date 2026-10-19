import type { Config } from "@/lib/types"

export type Band = 0 | 1 | 2 // 0 unknown, 1 likely, 2 confirmed
export type BallInfo = { poss: string; holder: [string, number] | null; band: Band; phase: string; phaseBand: Band }

const PHASE_LABEL: Record<string, string> = {
  goal_kick: "Goal kick", throw_in: "Throw-in", corner: "Corner", free_kick: "Free kick", kickoff: "Kick-off", keeper_hold: "Keeper has it",
}
export const isDeadBall = (p: string) => ["goal_kick", "throw_in", "corner", "free_kick"].includes(p)

/** Specific label when sure, generic "Set piece" (optionally "likely X") when not. */
export function phaseLabel(phase: string, band: number): string | null {
  if (phase === "open") return null
  if (phase === "kickoff" || phase === "keeper_hold") return PHASE_LABEL[phase]
  if (band === 2) return PHASE_LABEL[phase] ?? "Set piece"
  if (band === 1) return `Set piece · likely ${(PHASE_LABEL[phase] ?? "restart").toLowerCase()}`
  return "Set piece"
}

export const lastName = (full: string) => full.split(" ").slice(-1)[0]

export function describeBall(b: BallInfo, cfg: Config, codes: string[]): { text: string; teamIdx: number; band: Band } {
  const teamIdx = Math.max(0, codes.indexOf(b.poss))
  const team = b.poss || "-"
  const name = b.holder ? lastName(cfg.teams[b.holder[0]].players[b.holder[1]]) : ""
  const label = phaseLabel(b.phase, b.phaseBand)
  if (label && isDeadBall(b.phase)) {
    const who = b.band === 2 ? ` · ${name}` : b.band === 1 ? ` · taker likely ${name}` : " · taker unconfirmed"
    return { text: `${label} · ${team}${who}`, teamIdx, band: b.band }
  }
  if (label) return { text: `${label} · ${team}${b.band === 2 ? ` · ${name}` : ""}`, teamIdx, band: b.band }
  if (!b.holder || b.band === 0) return { text: b.holder ? `${team} in possession` : "Loose ball · contested", teamIdx, band: 0 }
  return { text: b.band === 2 ? `${team} · ${name}` : `${team} · likely ${name}`, teamIdx, band: b.band }
}
