import { motion } from 'motion/react'

/**
 * AnimatedCard integrates Motion/Animate UI card micro-interactions with smooth entry fade/slide
 * and subtle spring elevation on hover while retaining existing semantic roles and layout.
 */
export default function AnimatedCard({
  as: Component = 'article',
  children,
  className = '',
  delay = 0,
  hoverLift = true,
  ...props
}) {
  const MotionComponent = motion[Component] || motion.article

  return (
    <MotionComponent
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.28, delay, ease: [0.16, 1, 0.3, 1] }}
      whileHover={hoverLift ? { y: -3, transition: { duration: 0.18, ease: 'easeOut' } } : undefined}
      className={className}
      {...props}
    >
      {children}
    </MotionComponent>
  )
}
