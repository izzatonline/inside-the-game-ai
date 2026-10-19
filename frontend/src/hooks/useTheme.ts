import { useEffect, useState } from "react"

export type ThemeMode = "system" | "light" | "dark"
const KEY = "itg-theme"

export function readTheme(): ThemeMode {
  try { const v = localStorage.getItem(KEY); if (v === "light" || v === "dark" || v === "system") return v } catch { /* private mode */ }
  return "system"
}

export function applyTheme(mode: ThemeMode): boolean {
  const dark = mode === "dark" || (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", dark)
  document.documentElement.style.colorScheme = dark ? "dark" : "light"
  return dark
}

export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(readTheme)
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"))
  useEffect(() => {
    setDark(applyTheme(mode))
    try { localStorage.setItem(KEY, mode) } catch { /* ignore */ }
    if (mode !== "system") return
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const on = () => setDark(applyTheme("system"))
    mq.addEventListener("change", on)
    return () => mq.removeEventListener("change", on)
  }, [mode])
  return { mode, setMode, dark }
}
