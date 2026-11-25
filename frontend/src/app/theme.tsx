import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type ThemePref = 'light' | 'dark' | 'system'

const ThemeContext = createContext<{ pref: ThemePref; setPref: (p: ThemePref) => void; dark: boolean } | null>(
  null,
)

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem('fh-theme')
    return v === 'light' || v === 'dark' || v === 'system' ? v : 'dark'
  } catch {
    return 'dark'
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(readPref)
  const [systemDark, setSystemDark] = useState(() => matchMedia('(prefers-color-scheme: dark)').matches)

  useEffect(() => {
    const mq = matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const dark = pref === 'dark' || (pref === 'system' && systemDark)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  const setPref = (p: ThemePref) => {
    setPrefState(p)
    try {
      localStorage.setItem('fh-theme', p)
    } catch {
      /* armazenamento indisponível */
    }
  }

  return <ThemeContext.Provider value={{ pref, setPref, dark }}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme fora de ThemeProvider')
  return ctx
}
