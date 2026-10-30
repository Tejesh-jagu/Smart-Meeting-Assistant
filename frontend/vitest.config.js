import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      cn: fileURLToPath(new URL('./src/utils/cn.js', import.meta.url)),
    },
  },
  test: {
    include: ['src/**/*.test.{js,jsx}'],
    setupFiles: ['./src/utils/matchMediaPolyfill.js'],
  },
})
