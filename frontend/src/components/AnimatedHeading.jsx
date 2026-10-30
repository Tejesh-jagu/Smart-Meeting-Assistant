import ensureMatchMedia from '../utils/matchMediaPolyfill.js'
import {
  TypingText,
  TypingTextCursor,
} from '@animate-ui/react/primitives/texts/typing'

ensureMatchMedia()

export default function AnimatedHeading() {
  ensureMatchMedia()
  return (
    <span className="animated-hero-typing">
      <TypingText
        text={[
          'and reports, organized.',
          'with AI-powered summaries.',
          'from automatic transcription.',
        ]}
        loop
        holdDelay={2200}
      >
        <TypingTextCursor className="animated-cursor" />
      </TypingText>
    </span>
  )
}
