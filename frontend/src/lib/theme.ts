export const TEAM_COLORS = ["#38bdf8", "#f43f5e"]
/** Each match brings its own club colours: update the shared palette and the CSS variables the stylesheet reads. */
export function setTeamColors(c0: string, c1: string) {
  TEAM_COLORS[0] = c0
  TEAM_COLORS[1] = c1
  document.documentElement.style.setProperty("--team-0-b", c0)
  document.documentElement.style.setProperty("--team-1-b", c1)
}
export const BADGE_COLORS: Record<string, string> = {
  GK: "#94a3b8", CB: "#a5b4fc", FB: "#7dd3fc", IFB: "#fbbf24", OFB: "#34d399", DM: "#c4b5fd", B2B: "#67e8f9",
  A8: "#f9a8d4", CAM: "#fde68a", W: "#86efac", IW: "#fb923c", IF: "#fb923c", ST: "#fca5a5",
}

/** Team colour as [r, g, b] for canvas gradients and heatmaps. */
export const teamRgb = (i: number): number[] => {
  const h = TEAM_COLORS[i].replace("#", "")
  return [0, 2, 4].map((k) => parseInt(h.slice(k, k + 2), 16))
}
