import { Moon, Sun, SunMoon } from "lucide-react"
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarGroupLabel, SidebarHeader,
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarRail,
} from "@/components/ui/sidebar"
import type { ThemeMode } from "@/hooks/useTheme"
import { TEAM_COLORS } from "@/lib/theme"
import type { MatchInfo } from "@/lib/types"

type Props = { matches: MatchInfo[]; matchId: string; onSelect: (id: string) => void; theme: ThemeMode; onTheme: (m: ThemeMode) => void }

const NEXT: Record<ThemeMode, ThemeMode> = { system: "light", light: "dark", dark: "system" }
const THEME_LABEL: Record<ThemeMode, string> = { system: "Match my device", light: "Light mode", dark: "Dark mode" }

export function AppSidebar({ matches, matchId, onSelect, theme, onTheme }: Props) {
  const ThemeIcon = theme === "light" ? Sun : theme === "dark" ? Moon : SunMoon
  return (
    <Sidebar collapsible="offcanvas">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-1 py-1.5">
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-[#00ff85] to-[#04f5ff] text-base">⚽</span>
          <div className="grid leading-tight group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-extrabold tracking-tight">Inside the Game</span>
            <span className="text-sidebar-foreground/70 text-[11px]">Synthetic match intelligence</span>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Simulated matches</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {matches.map((m) => (
                <SidebarMenuItem key={m.id}>
                  <SidebarMenuButton size="lg" isActive={m.id === matchId} tooltip={`${m.title}: ${m.teams[0].name} v ${m.teams[1].name}`} onClick={() => onSelect(m.id)} className="h-auto items-start py-2">
                    <span className="mt-1 flex shrink-0 -space-x-1.5">
                      <span className="size-3.5 rounded-full ring-2 ring-sidebar" style={{ background: TEAM_COLORS[0] }} />
                      <span className="size-3.5 rounded-full ring-2 ring-sidebar" style={{ background: TEAM_COLORS[1] }} />
                    </span>
                    <span className="grid min-w-0 flex-1 text-left leading-snug">
                      <span className="truncate text-sm font-semibold">{m.title}</span>
                      <span className="text-sidebar-foreground/70 truncate text-xs">{m.teams[0].name} v {m.teams[1].name}</span>
                      <span className="text-sidebar-foreground/55 mt-0.5 line-clamp-2 text-[11px] whitespace-normal">{m.blurb}</span>
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip={THEME_LABEL[theme]} onClick={() => onTheme(NEXT[theme])}>
              <ThemeIcon /><span>{THEME_LABEL[theme]}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <p className="text-sidebar-foreground/70 px-2 pb-1 text-[10px] leading-snug group-data-[collapsible=icon]:hidden">All clubs, players and matches are invented. No real match data is used.</p>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
