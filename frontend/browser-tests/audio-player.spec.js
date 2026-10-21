import { expect, test } from '@playwright/test'

function makeWav() {
  const sampleRate = 8000
  const sampleCount = sampleRate * 2
  const buffer = Buffer.alloc(44 + sampleCount * 2)
  buffer.write('RIFF', 0)
  buffer.writeUInt32LE(36 + sampleCount * 2, 4)
  buffer.write('WAVE', 8)
  buffer.write('fmt ', 12)
  buffer.writeUInt32LE(16, 16)
  buffer.writeUInt16LE(1, 20)
  buffer.writeUInt16LE(1, 22)
  buffer.writeUInt32LE(sampleRate, 24)
  buffer.writeUInt32LE(sampleRate * 2, 28)
  buffer.writeUInt16LE(2, 32)
  buffer.writeUInt16LE(16, 34)
  buffer.write('data', 36)
  buffer.writeUInt32LE(sampleCount * 2, 40)

  for (let index = 0; index < sampleCount; index += 1) {
    buffer.writeInt16LE(Math.round(Math.sin((2 * Math.PI * 440 * index) / sampleRate) * 4000), 44 + index * 2)
  }

  return buffer
}

async function mockAuthenticatedSession(page) {
  await page.route('**/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'csrf-test' } }))
  await page.route('**/auth/me', (route) => route.fulfill({
    json: {
      user: { id: 1, name: 'Test User', email: 'test@example.com' },
      csrf_token: 'csrf-test',
    },
  }))
}

test('audio preview plays, pauses, seeks, and reports its real duration', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/transcripts', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: [] })
      return
    }
    await route.continue()
  })
  await page.route('**/reports', (route) => route.fulfill({ json: [] }))
  await page.goto('/')

  await page.getByLabel('Choose an audio file').setInputFiles({
    name: 'browser-check.wav',
    mimeType: 'audio/wav',
    buffer: makeWav(),
  })

  const audio = page.locator('audio')
  const seek = page.getByRole('slider', { name: 'Seek through audio' })
  await expect.poll(() => audio.evaluate((element) => element.duration)).toBeCloseTo(2, 1)
  await expect(seek).toHaveAttribute('aria-valuetext', '0:00 of 0:02')

  await page.getByRole('button', { name: 'Play audio' }).click()
  await expect(page.getByRole('button', { name: 'Pause audio' })).toHaveAttribute('aria-pressed', 'true')
  await expect.poll(() => audio.evaluate((element) => element.paused)).toBe(false)

  await page.getByRole('button', { name: 'Pause audio' }).click()
  await expect(page.getByRole('button', { name: 'Play audio' })).toHaveAttribute('aria-pressed', 'false')
  await expect.poll(() => audio.evaluate((element) => element.paused)).toBe(true)

  const bounds = await seek.boundingBox()
  await page.mouse.click(bounds.x + bounds.width * 0.7, bounds.y + bounds.height / 2)
  await expect.poll(() => audio.evaluate((element) => element.currentTime)).toBeGreaterThan(1)
  await expect(seek).toHaveAttribute('aria-valuetext', /of 0:02$/)
})

test('transcript save and report generation show progress and render the result', async ({ page }) => {
  const transcript = 'We agreed to review the launch plan. Priya will send the draft by Friday.'
  let saved = false
  await mockAuthenticatedSession(page)

  await page.route('**/transcripts', async (route) => {
    if (route.request().method() === 'POST') {
      await new Promise((resolve) => setTimeout(resolve, 350))
      saved = true
      await route.fulfill({ json: { id: 99, session_number: 1, message: 'Transcript saved.' } })
      return
    }

    await route.fulfill({
      json: saved
        ? [{ id: 99, session_number: 1, transcript, created_at: '2026-10-17T00:00:00Z' }]
        : [],
    })
  })
  await page.route('**/reports', (route) => route.fulfill({ json: [] }))
  await page.route('**/transcripts/99/report', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 350))
    await route.fulfill({
      json: {
        meeting_id: 99,
        summary: 'We agreed to review the launch plan.',
        decisions: ['We agreed to review the launch plan.'],
        tasks: ['Priya will send the draft by Friday.'],
        generator: 'Ollama llama3.2:3b',
        generated_at: '2026-10-17T00:00:00Z',
      },
    })
  })

  await page.goto('/')
  await page.getByText('No saved sessions yet').waitFor()
  await page.getByRole('textbox', { name: 'Meeting transcript' }).fill(transcript)
  await page.getByRole('button', { name: 'Save transcript' }).click()
  await expect(page.getByRole('button', { name: 'Saving transcript...' })).toBeDisabled()
  await expect(page.getByText(transcript)).toBeVisible()

  await page.getByRole('button', { name: 'Open session' }).click()
  await page.getByRole('button', { name: 'Generate report' }).click()
  await expect(page.getByRole('button', { name: 'Generating report...' })).toBeDisabled()
  const report = page.locator('.ai-report-card')
  await expect(report.getByRole('heading', { name: 'Meeting report' })).toBeVisible()
  await expect(report.getByRole('heading', { name: 'Summary' })).toBeVisible()
  await expect(report.getByRole('listitem').filter({
    hasText: /^We agreed to review the launch plan\.$/,
  })).toBeVisible()
  await expect(report.getByRole('listitem').filter({
    hasText: /^Priya will send the draft by Friday\.$/,
  })).toBeVisible()
})

test('mobile area navigation is usable and the workspace has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockAuthenticatedSession(page)
  await page.route('**/transcripts', (route) => route.fulfill({
    json: [{
      id: 123,
      session_number: 3,
      transcript: 'The team reviewed the launch plan and agreed to share a revised draft next week.',
      created_at: '2026-10-17T00:00:00Z',
    }],
  }))
  await page.route('**/reports', (route) => route.fulfill({
    json: [{
      meeting_id: 123,
      summary: 'The team reviewed the launch plan.',
      decisions: ['Continue with the revised launch plan.'],
      tasks: ['Share a revised draft next week.'],
      generator: 'Ollama llama3.2:3b',
      generated_at: '2026-10-17T00:00:00Z',
    }],
  }))
  await page.goto('/')
  await page.getByRole('button', { name: 'AI' }).click()
  await page.getByRole('heading', { name: 'AI workspace' }).waitFor()
  await expect(page.getByRole('button', { name: 'Download' })).toBeVisible()

  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 })
    const navigation = page.getByRole('navigation', { name: 'Main navigation' })
    await expect(navigation).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await navigation.getByRole('button', { name: 'Notes' }).click()
    await expect(page.getByRole('heading', { name: 'Notes & transcripts' })).toBeVisible()
    await navigation.getByRole('button', { name: 'AI' }).click()
    await expect(page.getByRole('heading', { name: 'AI workspace' })).toBeVisible()

    const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    expect(documentWidth).toBeLessThanOrEqual(width)
  }
})

test('manual and uploaded transcripts appear once with consecutive session labels', async ({ page }) => {
  const meetings = []
  await mockAuthenticatedSession(page)
  await page.route('**/transcripts', async (route) => {
    if (route.request().method() === 'POST') {
      const sessionNumber = meetings.length + 1
      meetings.unshift({
        id: sessionNumber,
        session_number: sessionNumber,
        transcript: (await route.request().postDataJSON()).transcript,
        created_at: '2026-10-17T00:00:00Z',
      })
      await route.fulfill({ json: { id: sessionNumber, session_number: sessionNumber, message: 'Transcript saved.' } })
      return
    }
    await route.fulfill({ json: meetings })
  })
  await page.route('**/transcripts/upload', async (route) => {
    const sessionNumber = meetings.length + 1
    const transcript = 'The team will share the revised agenda.'
    meetings.unshift({
      id: sessionNumber,
      session_number: sessionNumber,
      transcript,
      created_at: '2026-10-17T00:00:00Z',
    })
    await route.fulfill({
      json: { id: sessionNumber, session_number: sessionNumber, transcript, message: 'Audio transcribed and saved' },
    })
  })
  await page.route('**/reports', (route) => route.fulfill({ json: [] }))
  await page.goto('/')

  await page.getByRole('textbox', { name: 'Meeting transcript' }).fill('We agreed to update the agenda.')
  await page.getByRole('button', { name: 'Save transcript' }).click()
  await expect(page.getByRole('article', { name: 'Session 1' })).toHaveCount(1)

  await page.getByLabel('Choose an audio file').setInputFiles({
    name: 'session.wav',
    mimeType: 'audio/wav',
    buffer: makeWav(),
  })
  await page.getByRole('button', { name: 'Transcribe audio' }).click()
  await expect(page.getByRole('article', { name: 'Session 2' })).toHaveCount(1)
  await expect(page.getByRole('article')).toHaveCount(2)
})
