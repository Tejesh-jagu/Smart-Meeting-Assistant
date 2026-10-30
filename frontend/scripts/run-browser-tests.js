import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { setTimeout as delay } from 'node:timers/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function findAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address()
      server.close((error) => error ? reject(error) : resolve(port))
    })
  })
}

function waitForExit(child) {
  return new Promise((resolve) => child.once('exit', resolve))
}

async function waitForFrontend(child, url) {
  const deadline = Date.now() + 60_000

  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error('Vite stopped before becoming ready.')

    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // The development server has not opened its port yet.
    }

    await delay(250)
  }

  throw new Error('Timed out waiting for the Vite test server.')
}

const port = await findAvailablePort()
const url = `http://127.0.0.1:${port}`
// Mocked API calls must not fall through to a real local backend.
const vite = spawn(process.execPath, [
  path.join(frontendDir, 'node_modules/vite/bin/vite.js'),
  '--host', '127.0.0.1', '--port', String(port), '--strictPort',
], { cwd: frontendDir, stdio: 'inherit', env: { ...process.env, VITE_API_PORT: '1' } })
let runner

try {
  await waitForFrontend(vite, url)
  runner = spawn(process.execPath, [
    path.join(frontendDir, 'node_modules/@playwright/test/cli.js'),
    'test',
  ], {
    cwd: frontendDir,
    stdio: 'inherit',
    env: { ...process.env, SMART_MEETING_FRONTEND_URL: url },
  })
  process.exitCode = await waitForExit(runner)
} catch (error) {
  process.stderr.write(`${error.message}\n`)
  process.exitCode = 1
} finally {
  if (runner && runner.exitCode === null) runner.kill()
  if (vite.exitCode === null) {
    const viteExit = waitForExit(vite)
    vite.kill()
    await Promise.race([viteExit, delay(5000)])
  }
}
