import { motion } from 'motion/react'
import { Lock, Wallet } from 'lucide-react'
import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/app/auth'
import { Button } from '@/components/ui/button'
import { Field, Input } from '@/components/ui/field'
import { easeOut } from '@/lib/motion'

export function LoginPage() {
  const { session, signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (session) return <Navigate to="/" replace />

  return (
    <div className="grid min-h-dvh place-items-center bg-bg px-4">
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: easeOut }}
        className="w-full max-w-sm"
      >
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <span className="grid size-12 place-items-center rounded-2xl bg-fg text-bg shadow-pop">
            <Wallet className="size-6" aria-hidden />
          </span>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Finance Hub</h1>
            <p className="mt-1 text-sm text-muted">Acesso exclusivo do proprietário.</p>
          </div>
        </div>

        <form
          className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6 shadow-card"
          onSubmit={async (e) => {
            e.preventDefault()
            setLoading(true)
            setError(await signIn(email.trim(), password))
            setLoading(false)
          }}
        >
          <Field label="E-mail">
            {(p) => (
              <Input {...p} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            )}
          </Field>
          <Field label="Senha" error={error ?? undefined}>
            {(p) => (
              <Input
                {...p}
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          <Button type="submit" size="lg" loading={loading} className="mt-1">
            <Lock /> Entrar
          </Button>
        </form>
        <p className="mt-6 text-center text-xs text-muted">Não há cadastro público. Aplicação privada de uso individual.</p>
      </motion.div>
    </div>
  )
}
