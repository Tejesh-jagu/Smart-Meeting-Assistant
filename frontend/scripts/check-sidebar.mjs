import { chromium } from '@playwright/test'

async function check() {
  const browser = await chromium.launch()
  const page = await browser.newPage()

  await page.route('**/auth/csrf', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'test' }) }))
  await page.route('**/auth/me', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ user: { id: 1, name: 'Tejesh', email: 't@ex.com' }, csrf_token: 'test' }) }))
  await page.route('**/transcripts', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }))
  await page.route('**/reports', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }))

  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
  await page.waitForTimeout(600)

  // Check sidebar CSS position
  const sidebarPos = await page.evaluate(() => {
    const sidebar = document.querySelector('.workspace-sidebar')
    if (!sidebar) return null
    const cs = window.getComputedStyle(sidebar)
    return { position: cs.position, width: cs.width, height: cs.height, top: cs.top, left: cs.left }
  })
  console.log('Sidebar computed style:', JSON.stringify(sidebarPos))

  // Screenshot at top of page
  await page.screenshot({ path: 'scripts/sidebar_top.png', fullPage: false })

  // Scroll down
  await page.evaluate(() => window.scrollBy(0, 500))
  await page.waitForTimeout(300)
  await page.screenshot({ path: 'scripts/sidebar_scrolled.png', fullPage: false })

  await browser.close()
}

check().catch(console.error)
