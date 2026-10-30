import ensureMatchMedia from '../../utils/matchMediaPolyfill.js'
import { Button } from '@animate-ui/react/primitives/buttons/button'

ensureMatchMedia()

/**
 * AnimatedButton integrates Animate UI's Button primitive with spring physics,
 * tactile tap feedback, and hover scale while preserving native button semantics and classes.
 */
export default function AnimatedButton({
  hoverScale = 1.02,
  tapScale = 0.96,
  className = '',
  type = 'button',
  children,
  ...props
}) {
  ensureMatchMedia()
  return (
    <Button
      hoverScale={hoverScale}
      tapScale={tapScale}
      type={type}
      className={className}
      {...props}
    >
      {children}
    </Button>
  )
}
