// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import GlyphBackgroundDemo from './GlyphBackgroundDemo.jsx'
import { GlyphBackground } from './animate-ui/backgrounds/glyph.jsx'

describe('GlyphBackground components', () => {
  it('renders GlyphBackground without throwing', () => {
    const { container } = render(
      <GlyphBackground
        glowColor="#34d399"
        shapeColor="#3b9eff"
        fontSize={12}
        interactive={true}
      >
        <span data-testid="child-content">Glyph Child</span>
      </GlyphBackground>
    )

    const bg = container.querySelector('[data-slot="glyph-background"]')
    expect(bg).not.toBeNull()
    const canvas = container.querySelector('canvas')
    expect(canvas).not.toBeNull()
    expect(container.textContent).toContain('Glyph Child')
  })

  it('renders GlyphBackgroundDemo with custom props and default options', () => {
    const { container } = render(
      <GlyphBackgroundDemo
        glowColor="#a78bfa"
        shapeColor="#fbbf24"
        fontSize={14}
        interactive="true"
      />
    )

    const bg = container.querySelector('[data-slot="glyph-background"]')
    expect(bg).not.toBeNull()
    expect(bg.className).toContain('absolute')
    expect(bg.className).toContain('inset-0')
    const canvas = container.querySelector('canvas')
    expect(canvas).not.toBeNull()
  })
})
