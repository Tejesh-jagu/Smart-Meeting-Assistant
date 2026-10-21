import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './browser-tests',
  reporter: 'list',
  use: {
    baseURL: process.env.SMART_MEETING_FRONTEND_URL || 'http://127.0.0.1:4179',
    browserName: 'chromium',
    headless: true,
  },
})
