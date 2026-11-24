import type { Transition, Variants } from 'motion/react'

// Curvas e durações centralizadas: entrada ~220ms, saída mais curta (~140ms), sem overshoot em dados.
export const easeOut = [0.22, 1, 0.36, 1] as const
export const easeIn = [0.4, 0, 1, 1] as const

export const spring: Transition = { type: 'spring', stiffness: 420, damping: 36, mass: 0.8 }

export const pageVariants: Variants = {
  initial: { opacity: 0, y: 10, filter: 'blur(3px)' },
  enter: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.24, ease: easeOut } },
  exit: { opacity: 0, y: -6, filter: 'blur(2px)', transition: { duration: 0.14, ease: easeIn } },
}

export const staggerContainer: Variants = {
  initial: {},
  enter: { transition: { staggerChildren: 0.045, delayChildren: 0.04 } },
}

export const riseItem: Variants = {
  initial: { opacity: 0, y: 12 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.32, ease: easeOut } },
}

export const listItem: Variants = {
  initial: { opacity: 0, y: 6 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.22, ease: easeOut } },
  exit: { opacity: 0, x: -12, transition: { duration: 0.14, ease: easeIn } },
}
