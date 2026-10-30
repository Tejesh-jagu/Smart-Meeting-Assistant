import { useEffect } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import AnimatedButton from './AnimatedButton.jsx'

/**
 * AnimatedDialog provides an accessible, animated modal dialog primitive
 * with spring physics, backdrop blur, keyboard dismissal, and smooth exit animations.
 */
export default function AnimatedDialog({
  isOpen,
  onClose,
  title,
  description,
  children,
  confirmText,
  cancelText = 'Cancel',
  onConfirm,
  confirmVariant = 'danger',
}) {
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape' && isOpen) {
        onClose?.()
      }
    }
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown)
    }
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="animated-dialog-portal" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
          <motion.div
            className="animated-dialog-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <div className="animated-dialog-wrapper">
            <motion.div
              className="animated-dialog-content"
              initial={{ opacity: 0, scale: 0.94, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 10 }}
              transition={{ type: 'spring', damping: 25, stiffness: 320 }}
            >
              {title && <h3 id="dialog-title" className="animated-dialog-title">{title}</h3>}
              {description && <p className="animated-dialog-description">{description}</p>}
              {children}
              <div className="animated-dialog-actions">
                <AnimatedButton className="button button--secondary" onClick={onClose}>
                  {cancelText}
                </AnimatedButton>
                {confirmText && (
                  <AnimatedButton
                    className={`button button--${confirmVariant}`}
                    onClick={() => {
                      onConfirm?.()
                      onClose?.()
                    }}
                  >
                    {confirmText}
                  </AnimatedButton>
                )}
              </div>
            </motion.div>
          </div>
        </div>
      )}
    </AnimatePresence>
  )
}
