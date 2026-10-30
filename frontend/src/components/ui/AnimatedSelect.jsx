import { useState } from 'react'
import { motion } from 'motion/react'

/**
 * AnimatedSelect wraps native <select> elements with smooth micro-interactions,
 * animated chevron rotation, and spring border highlight while ensuring 100% compatibility
 * with standard accessibility attributes and userEvent testing.
 */
export default function AnimatedSelect({
  id,
  value,
  onChange,
  children,
  className = '',
  ...props
}) {
  const [isFocused, setIsFocused] = useState(false)

  return (
    <motion.div
      className={`animated-select-container ${isFocused ? 'is-focused' : ''} ${className}`}
      whileHover={{ scale: 1.01 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
    >
      <select
        id={id}
        value={value}
        onChange={onChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        className="animated-select-element"
        {...props}
      >
        {children}
      </select>
      <motion.span
        className="animated-select-chevron"
        animate={{ rotate: isFocused ? 180 : 0 }}
        transition={{ type: 'spring', stiffness: 350, damping: 22 }}
        aria-hidden="true"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </motion.span>
    </motion.div>
  )
}
