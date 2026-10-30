"use client"

import { GlyphBackground } from "@/components/animate-ui/backgrounds/glyph"

const COLORS = {
  text: "",
  white: "#ffffff",
  blue: "#3b9eff",
  violet: "#a78bfa",
  emerald: "#34d399",
  amber: "#fbbf24",
  rose: "#fb7185",
}

export default function GlyphBackgroundDemo({
  glowColor = "",
  shapeColor = "",
  fontSize = 10,
  interactive = true,
  className = "",
  children,
  ...props
}) {
  return (
    <GlyphBackground
      className={`absolute inset-0 bg-white text-neutral-900 dark:bg-[#121212] dark:text-white ${className}`.trim()}
      glowColor={glowColor || undefined}
      shapeColor={shapeColor || undefined}
      fontSize={Number(fontSize)}
      interactive={interactive === true || interactive === "true"}
      {...props}
    >
      {children}
    </GlyphBackground>
  )
}

GlyphBackgroundDemo.COLORS = COLORS
