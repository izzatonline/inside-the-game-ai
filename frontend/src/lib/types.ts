export type Chip = { label: string; value: string }
export type Overlay = {
  moment_id: string; t: number; minute: number; kind: string; team: string; importance: number
  headline: string; body: string; why: string; chips: Chip[]; lang: string; mode: string
  source: string; verified: boolean; player?: string | null
  facts?: Record<string, unknown>; model?: string
  check?: { how: string; numbers: number; matched: number; unmatched: string[]; agents: string[] }
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
  passes: number; shots_off: number; shots_blocked: number; saves: number; corners: number; free_kicks: number; throw_ins: number
  goal_kicks: number; fouls: number; yellow: number; offsides: number; crosses: number; tackles: number; interceptions: number; pressures: number
}
export type PlayerStat = {
  team: string; passes: number; passes_ok: number; pass_acc: number; pass_diff: number; shots: number; on_target: number; goals: number; assists: number
  xg: number; sprints: number; top_speed: number; tackles: number; interceptions: number; pressures: number
}
export type Stats = { t: number; minute: number; momentum: number; teams: Record<string, TeamStats>; players?: Record<string, PlayerStat> }
export type GoalLog = { minute: number; team: string; player: string; score_home: number; score_away: number; og?: boolean }
export type CardLog = { minute: number; team: string; player: string; card: string }
export type SubLog = { minute: number; team: string; slot: number; player_in: string; player_out: string; number: number }
export type Report = {
  heat: { cols: number; rows: number; v: number[][]; w: number[][] }
  tilt: Record<string, number>
  metrics: { key: string; label: string; unit: string; home: number; away: number }[]
}
export type Recap = {
  headline: string; body: string; source: string; stats: Record<string, TeamStats>; home: string; away: string
  report: Report; goals: GoalLog[]; cards: CardLog[]; subs: SubLog[]; key_moments: { minute: number; kind: string; headline: string; team: string }[]
}
export type Staff = { coach: string; assistants: string[]; subs: { name: string; pos: string; number: number }[] }
export type BenchState = Record<string, { warming: number[]; used: number[] }>
export type BenchPick = { team: number; name: string; role: string } | null
export type Config = {
  llm: string; orchestration: string; languages: Record<string, string>; match: { id: string; title: string; subtitle: string; duration_min: number; stadium: string }
  teams: Record<string, { name: string; color: string; players: string[]; numbers: number[]; slots: number[][]; formation: string; lines: number[][]; staff: Staff }>
  referee: { name: string; assistants: string[]; var: string }
}
export type MatchInfo = { id: string; title: string; subtitle: string; blurb: string; duration_min: number; stadium: string; scripted: boolean; teams: { code: string; name: string; color: string }[] }
export type Settings = {
  match: string; mode: string; lang: string; team: string; player: string; metric: string; src: string; speed: string; seed: string; ai: string
}
export type Frames = {
  target: number[][] | null; ball: number[]; trail: number[][]; n: number; reset: boolean
  holder: [string, number] | null; band: 0 | 1 | 2; phase: string; phaseBand: 0 | 1 | 2; poss: string
  lastConfirmed: { team: string; idx: number; at: number } | null
  goal: { team: string; at: number } | null
}
export type Selected = { team: number; idx: number } | null
