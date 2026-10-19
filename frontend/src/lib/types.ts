export type Chip = { label: string; value: string }
export type Overlay = {
  moment_id: string; t: number; minute: number; kind: string; team: string; importance: number
  headline: string; body: string; why: string; chips: Chip[]; lang: string; mode: string
  source: string; verified: boolean
}
export type Role = { idx: number; name: string; role: string; short: string; x_in: number; y_in: number }
export type TeamTactics = {
  name: string; formation: string; line_height: number; width_m: number; hull_area: number; ppda: number
  long_pct: number; wide_pct: number; tags: string[]; primary: string; roles: Role[]
  options: { title: string; detail: string }[]; summary?: string; summary_source?: string
}
export type TacticsMap = Record<string, TeamTactics>
export type TeamStats = {
  name: string; goals: number; possession_pct: number; shots: number; on_target: number; xg: number; pass_acc_pct: number
}
export type Stats = { t: number; minute: number; momentum: number; teams: Record<string, TeamStats> }
export type Recap = { headline: string; body: string; source: string }
export type Config = {
  llm: string; orchestration: string; languages: Record<string, string>
  teams: Record<string, { name: string; players: string[] }>
}
export type Settings = {
  mode: string; lang: string; team: string; player: string; metric: string; src: string; speed: string; seed: string
}
export type Frames = {
  target: number[][] | null; ball: number[]; trail: number[][]; n: number; reset: boolean
  holder: [string, number] | null; band: 0 | 1 | 2; phase: string; phaseBand: 0 | 1 | 2; poss: string
  lastConfirmed: { team: string; idx: number; at: number } | null
}
export type Selected = { team: number; idx: number } | null
