import { Dialog as D } from 'radix-ui'
import { AnimatePresence, motion } from 'motion/react'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { easeIn, easeOut } from '@/lib/motion'
import { cn } from '@/lib/utils'

interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: ReactNode
  className?: string
}

/** Modal acessível (Radix) com entrada/saída animadas; no celular abre como folha inferior. */
export function Dialog({ open, onOpenChange, title, description, children, className }: DialogProps) {
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <D.Portal forceMount>
            <D.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px]"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1, transition: { duration: 0.2 } }}
                exit={{ opacity: 0, transition: { duration: 0.15 } }}
              />
            </D.Overlay>
            <D.Content asChild forceMount>
              <motion.div
                className={cn(
                  'fixed z-50 flex max-h-[92dvh] w-full flex-col overflow-hidden border border-border bg-surface shadow-pop outline-none',
                  'inset-x-0 bottom-0 rounded-t-2xl sm:inset-auto sm:top-1/2 sm:left-1/2 sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl',
                  className,
                )}
                initial={{ opacity: 0, y: 24, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1, transition: { duration: 0.26, ease: easeOut } }}
                exit={{ opacity: 0, y: 16, scale: 0.985, transition: { duration: 0.15, ease: easeIn } }}
              >
                <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
                  <div>
                    <D.Title className="text-base font-semibold tracking-tight">{title}</D.Title>
                    {description ? (
                      <D.Description className="mt-0.5 text-[13px] text-muted">{description}</D.Description>
                    ) : (
                      <D.Description className="sr-only">{title}</D.Description>
                    )}
                  </div>
                  <D.Close
                    className="-mr-1 grid size-8 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-fg"
                    aria-label="Fechar"
                  >
                    <X className="size-4" />
                  </D.Close>
                </div>
                <div className="overflow-y-auto px-5 py-4">{children}</div>
              </motion.div>
            </D.Content>
          </D.Portal>
        )}
      </AnimatePresence>
    </D.Root>
  )
}
