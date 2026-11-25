import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { Tooltip } from 'radix-ui'
import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Navigate, RouterProvider, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AuthProvider, useAuth } from '@/app/auth'
import { AppLayout } from '@/app/layout'
import { ThemeProvider, useTheme } from '@/app/theme'
import { ApiError } from '@/lib/api'
import { AccountDetailPage, AccountsPage } from '@/pages/accounts'
import { BillsPage } from '@/pages/bills'
import { CalendarPage } from '@/pages/calendar'
import { CardsPage } from '@/pages/cards'
import { CardDetailPage } from '@/pages/card-detail'
import { ComingSoonPage } from '@/pages/coming-soon'
import { DashboardPage } from '@/pages/dashboard'
import { LoginPage } from '@/pages/login'
import { PeoplePage } from '@/pages/people'
import { SettingsPage } from '@/pages/settings'
import { TransactionsPage } from '@/pages/transactions'
import './index.css'

const queryClient: QueryClient = new QueryClient({
  // Qualquer mutação bem-sucedida pode alterar vencimentos: o calendário é sempre revalidado.
  mutationCache: new MutationCache({
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['calendar'] }),
  }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
})

function RequireOwner({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="grid min-h-dvh place-items-center"><div className="shimmer size-10 rounded-xl" /></div>
  if (!session) return <Navigate to="/entrar" replace state={{ from: location }} />
  return <>{children}</>
}

const router = createBrowserRouter([
  { path: '/entrar', element: <LoginPage /> },
  {
    element: (
      <RequireOwner>
        <AppLayout />
      </RequireOwner>
    ),
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/lancamentos', element: <TransactionsPage /> },
      { path: '/contas', element: <AccountsPage /> },
      { path: '/contas/:id', element: <AccountDetailPage /> },
      { path: '/cartoes', element: <CardsPage /> },
      { path: '/cartoes/:id', element: <CardDetailPage /> },
      { path: '/contas-da-casa', element: <BillsPage /> },
      { path: '/calendario', element: <CalendarPage /> },
      { path: '/em-breve/calendario', element: <Navigate to="/calendario" replace /> },
      { path: '/pessoas', element: <PeoplePage /> },
      { path: '/configuracoes', element: <SettingsPage /> },
      { path: '/em-breve/:mod', element: <ComingSoonPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])

function ThemedToaster() {
  const { dark } = useTheme()
  return <Toaster position="top-right" theme={dark ? 'dark' : 'light'} richColors closeButton />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <MotionConfig reducedMotion="user">
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <Tooltip.Provider>
              <RouterProvider router={router} />
              <ThemedToaster />
            </Tooltip.Provider>
          </AuthProvider>
        </QueryClientProvider>
      </MotionConfig>
    </ThemeProvider>
  </StrictMode>,
)
