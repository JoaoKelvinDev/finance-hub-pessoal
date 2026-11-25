import { AnimatePresence, motion } from 'motion/react'
import {
  ArrowLeftRight,
  CalendarDays,
  ChartPie,
  CreditCard,
  HandCoins,
  LayoutDashboard,
  LogOut,
  Monitor,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Receipt,
  Settings,
  Sun,
  Target,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { createContext, useContext, useState } from 'react'
import { NavLink, useLocation, useOutlet } from 'react-router-dom'
import { useAuth } from '@/app/auth'
import { useTheme, type ThemePref } from '@/app/theme'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/misc'
import { AlertsBell } from '@/features/alerts/AlertsBell'
import { NewTransactionDialog, type NewKind } from '@/features/transactions/new-transaction-dialog'
import { pageVariants, spring } from '@/lib/motion'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  stage?: number
}

const NAV: { section?: string; items: NavItem[] }[] = [
  {
    items: [
      { to: '/', label: 'Visão geral', icon: LayoutDashboard },
      { to: '/lancamentos', label: 'Lançamentos', icon: ArrowLeftRight },
      { to: '/contas', label: 'Contas e carteiras', icon: Wallet },
      { to: '/cartoes', label: 'Cartões', icon: CreditCard },
      { to: '/contas-da-casa', label: 'Contas da casa', icon: Receipt },
      { to: '/calendario', label: 'Calendário', icon: CalendarDays },
      { to: '/terceiros', label: 'Valores com terceiros', icon: HandCoins },
      { to: '/planejamento', label: 'Planejamento', icon: Target },
      { to: '/pessoas', label: 'Pessoas', icon: Users },
    ],
  },
  {
    section: 'Próximas etapas',
    items: [
      { to: '/em-breve/relatorios', label: 'Relatórios', icon: ChartPie, stage: 5 },
    ],
  },
]

const TITLES: Record<string, string> = {
  '/': 'Visão geral',
  '/lancamentos': 'Lançamentos',
  '/contas': 'Contas e carteiras',
  '/cartoes': 'Cartões',
  '/contas-da-casa': 'Contas da casa',
  '/calendario': 'Calendário financeiro',
  '/terceiros': 'Valores com terceiros',
  '/planejamento': 'Planejamento',
  '/pessoas': 'Pessoas',
  '/configuracoes': 'Configurações',
}

const QuickAdd = createContext<(k?: NewKind) => void>(() => {})
export const useQuickAdd = () => useContext(QuickAdd)

function readCollapsed() {
  try {
    return localStorage.getItem('fh-sidebar') !== '0'
  } catch {
    return true
  }
}

export function AppLayout() {
  const location = useLocation()
  const outlet = useOutlet()
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [newOpen, setNewOpen] = useState(false)
  const [newKind, setNewKind] = useState<NewKind>('EXPENSE')

  const toggle = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem('fh-sidebar', c ? '0' : '1')
      } catch {
        /* sem armazenamento */
      }
      return !c
    })
  }

  const openNew = (k: NewKind = 'EXPENSE') => {
    setNewKind(k)
    setNewOpen(true)
  }

  const title =
    TITLES[location.pathname] ??
    (location.pathname.startsWith('/contas/')
      ? 'Extrato da conta'
      : location.pathname.startsWith('/pessoas/')
        ? 'Contato'
        : location.pathname.startsWith('/em-breve')
          ? 'Em breve'
          : '')
  // Chave por seção: navegar entre abas/filtros da mesma página não dispara transição de tela.
  const pageKey = '/' + (location.pathname.split('/')[1] ?? '') + (/^\/(contas|pessoas)\/./.test(location.pathname) ? '/detalhe' : '')

  return (
    <QuickAdd.Provider value={openNew}>
      <div className="flex min-h-dvh">
        <motion.aside
          initial={false}
          animate={{ width: collapsed ? 72 : 248 }}
          transition={spring}
          className="sticky top-3 my-3 ml-3 hidden h-[calc(100dvh-1.5rem)] shrink-0 flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-card md:flex"
        >
          <div className="flex h-16 items-center gap-2.5 px-4">
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-violet-400 to-violet-700 text-white shadow-[0_6px_18px_-6px_rgb(139_92_246/0.7)]">
              <Wallet className="size-[18px]" aria-hidden />
            </span>
            <AnimatePresence initial={false}>
              {!collapsed && (
                <motion.span
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0, transition: { delay: 0.06 } }}
                  exit={{ opacity: 0, transition: { duration: 0.08 } }}
                  className="text-[15px] font-semibold tracking-tight whitespace-nowrap"
                >
                  Finance Hub
                </motion.span>
              )}
            </AnimatePresence>
          </div>

          <nav className="flex-1 overflow-x-hidden overflow-y-auto px-3 py-2" aria-label="Navegação principal">
            {NAV.map((group, gi) => (
              <div key={gi} className={cn(gi > 0 && 'mt-5')}>
                {group.section && (
                  <p className={cn('mb-1 px-3 text-[11px] font-medium tracking-wide text-muted/80 uppercase', collapsed && 'sr-only')}>
                    {group.section}
                  </p>
                )}
                <ul className="space-y-0.5">
                  {group.items.map((item) => (
                    <li key={item.to}>
                      <SideLink item={item} collapsed={collapsed} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>

          <div className="border-t border-border p-3">
            <SideLink item={{ to: '/configuracoes', label: 'Configurações', icon: Settings }} collapsed={collapsed} />
            <button
              onClick={toggle}
              className="mt-0.5 flex h-9 w-full items-center gap-3 rounded-lg px-3 text-sm text-muted hover:bg-surface-2 hover:text-fg"
              aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
            >
              {collapsed ? <PanelLeftOpen className="size-4 shrink-0" /> : <PanelLeftClose className="size-4 shrink-0" />}
              {!collapsed && <span className="whitespace-nowrap">Recolher</span>}
            </button>
          </div>
        </motion.aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-16 items-center gap-3 bg-bg/70 px-4 backdrop-blur-md sm:px-6">
            <AnimatePresence mode="wait" initial={false}>
              <motion.h1
                key={title}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0, transition: { duration: 0.2 } }}
                exit={{ opacity: 0, y: -6, transition: { duration: 0.12 } }}
                className="truncate text-lg font-semibold tracking-tight"
              >
                {title}
              </motion.h1>
            </AnimatePresence>
            <div className="ml-auto flex items-center gap-1.5">
              <Button onClick={() => openNew()} className="hidden sm:inline-flex">
                <Plus /> Novo lançamento
              </Button>
              <AlertsBell />
              <ThemeToggle />
              <SignOutButton />
            </div>
          </header>

          <main className="relative flex-1 px-4 pt-5 pb-28 sm:px-6 md:pb-10">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={pageKey} variants={pageVariants} initial="initial" animate="enter" exit="exit">
                {outlet}
              </motion.div>
            </AnimatePresence>
          </main>
        </div>

        <MobileNav onNew={() => openNew()} />
        <NewTransactionDialog open={newOpen} onOpenChange={setNewOpen} initialKind={newKind} />
      </div>
    </QuickAdd.Provider>
  )
}

function SideLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const Icon = item.icon
  const link = (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'relative flex h-9 items-center gap-3 rounded-lg px-3 text-sm whitespace-nowrap',
          isActive ? 'font-medium text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg',
          item.stage && 'text-muted/70',
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="sidebar-active"
              transition={spring}
              className="absolute inset-0 rounded-lg bg-accent-soft ring-1 ring-accent/25"
            />
          )}
          <Icon className={cn('relative size-4 shrink-0', isActive && 'text-accent')} aria-hidden />
          {!collapsed && <span className="relative flex-1 truncate">{item.label}</span>}
          {!collapsed && item.stage && (
            <span className="relative rounded-md bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-muted">
              Etapa {item.stage}
            </span>
          )}
          {collapsed && <span className="sr-only">{item.label}</span>}
        </>
      )}
    </NavLink>
  )
  // O Trigger do tooltip (asChild) concatena className como texto; como o NavLink usa uma função
  // de classes, ele as perderia (inclusive o `relative`). O span recebe as props do Trigger no lugar.
  return collapsed ? (
    <Tooltip content={item.label + (item.stage ? ` (Etapa ${item.stage})` : '')}>
      <span className="block">{link}</span>
    </Tooltip>
  ) : (
    link
  )
}

function MobileNav({ onNew }: { onNew: () => void }) {
  const items: NavItem[] = [
    { to: '/', label: 'Início', icon: LayoutDashboard },
    { to: '/lancamentos', label: 'Lançamentos', icon: ArrowLeftRight },
    { to: '/calendario', label: 'Agenda', icon: CalendarDays },
    { to: '/contas', label: 'Contas', icon: Wallet },
    { to: '/cartoes', label: 'Cartões', icon: CreditCard },
    { to: '/contas-da-casa', label: 'Casa', icon: Receipt },
    { to: '/configuracoes', label: 'Ajustes', icon: Settings },
  ]
  const left = items.slice(0, 3)
  const right = items.slice(3)
  const renderItem = (item: NavItem) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn('relative flex flex-1 flex-col items-center gap-1 py-2 text-[11px]', isActive ? 'text-fg' : 'text-muted')
      }
    >
      {({ isActive }) => (
        <>
          {isActive && <motion.span layoutId="mobile-active" transition={spring} className="absolute top-0 h-0.5 w-8 rounded-full bg-accent" />}
          <item.icon className="size-5" aria-hidden />
          {item.label}
        </>
      )}
    </NavLink>
  )
  return (
    <nav
      aria-label="Navegação"
      className="fixed inset-x-0 bottom-0 z-40 flex items-stretch border-t border-border bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
    >
      {left.map(renderItem)}
      <div className="flex flex-1 items-center justify-center">
        <motion.button
          whileTap={{ scale: 0.92 }}
          onClick={onNew}
          aria-label="Novo lançamento"
          className="-mt-6 grid size-14 place-items-center rounded-2xl bg-accent text-accent-fg shadow-pop"
        >
          <Plus className="size-6" />
        </motion.button>
      </div>
      {right.map(renderItem)}
    </nav>
  )
}

function ThemeToggle() {
  const { pref, setPref } = useTheme()
  const order: ThemePref[] = ['system', 'light', 'dark']
  const next = order[(order.indexOf(pref) + 1) % order.length]
  const Icon = pref === 'dark' ? Moon : pref === 'light' ? Sun : Monitor
  const label = { system: 'Tema do sistema', light: 'Tema claro', dark: 'Tema escuro' }[pref]
  return (
    <Tooltip content={`${label} — clique para alternar`}>
      <Button variant="ghost" size="icon" onClick={() => setPref(next)} aria-label={`${label}. Alternar tema`}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={pref}
            initial={{ rotate: -90, opacity: 0 }}
            animate={{ rotate: 0, opacity: 1 }}
            exit={{ rotate: 90, opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <Icon className="size-[18px]" />
          </motion.span>
        </AnimatePresence>
      </Button>
    </Tooltip>
  )
}

function SignOutButton() {
  const { signOut } = useAuth()
  return (
    <Tooltip content="Sair">
      <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sair">
        <LogOut className="size-[18px]" />
      </Button>
    </Tooltip>
  )
}
