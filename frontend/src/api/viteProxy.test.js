// @vitest-environment node
import { createServer as createHttpServer, request as sendHttpRequest } from 'node:http'
import { afterEach, expect, it } from 'vitest'
import { createServer as createViteServer } from 'vite'
import { createViteConfig } from '../../vite.config.js'

let upstream
let frontend

function sendRequest(port, hostname, path, options = {}) {
  return new Promise((resolve, reject) => {
    const request = sendHttpRequest({
      hostname: '127.0.0.1',
      port,
      path,
      method: options.method || 'GET',
      headers: { host: hostname, ...options.headers },
    }, (response) => {
      const chunks = []
      response.on('data', (chunk) => chunks.push(chunk))
      response.on('end', () => resolve({
        status: response.statusCode,
        headers: response.headers,
        body: Buffer.concat(chunks).toString(),
      }))
    })
    request.on('error', reject)
    if (options.body) request.write(options.body)
    request.end()
  })
}

afterEach(async () => {
  await frontend?.close()
  if (upstream?.listening) {
    await new Promise((resolve) => upstream.close(resolve))
  }
  frontend = undefined
  upstream = undefined
})

it('keeps Vite host access exact and validates the local API port', () => {
  const config = createViteConfig({ NGROK_HOSTNAME: 'Demo.ngrok-free.app' })
  const proxyPattern = new RegExp(Object.keys(config.server.proxy)[0])

  expect(config.server.host).toBe('localhost')
  expect(config.server.allowedHosts).toEqual(['demo.ngrok-free.app'])
  expect(['/auth/csrf', '/transcripts', '/reports', '/health'].every((path) => proxyPattern.test(path))).toBe(true)
  expect(proxyPattern.test('/assets/app.js')).toBe(false)
  expect(createViteConfig({}).server.allowedHosts).toEqual([])
  expect(() => createViteConfig({ NGROK_HOSTNAME: '*.ngrok-free.app' })).toThrow(/exact hostname/)
  expect(() => createViteConfig({ VITE_API_PORT: 'abc' })).toThrow(/valid local TCP port/)
})

it('proxies same-origin auth requests while preserving CSRF, cookies, and response cookies', async () => {
  let received
  upstream = createHttpServer((request, response) => {
    const chunks = []
    request.on('data', (chunk) => chunks.push(chunk))
    request.on('end', () => {
      received = {
        method: request.method,
        url: request.url,
        host: request.headers.host,
        origin: request.headers.origin,
        cookie: request.headers.cookie,
        csrf: request.headers['x-csrf-token'],
        body: Buffer.concat(chunks).toString(),
      }
      response.writeHead(200, {
        'content-type': 'application/json',
        'set-cookie': 'sma_session=demo; Path=/; HttpOnly; Secure; SameSite=Lax',
      })
      response.end(JSON.stringify({ ok: true }))
    })
  })
  await new Promise((resolve) => upstream.listen(0, '127.0.0.1', resolve))

  const hostname = 'demo.ngrok-free.app'
  const config = createViteConfig({
    NGROK_HOSTNAME: hostname,
    VITE_API_PORT: String(upstream.address().port),
  })
  frontend = await createViteServer({
    configFile: false,
    root: process.cwd(),
    logLevel: 'silent',
    plugins: config.plugins,
    server: { ...config.server, host: '127.0.0.1', port: 0, strictPort: false, hmr: false },
  })
  await frontend.listen()

  const port = frontend.httpServer.address().port
  const response = await sendRequest(port, hostname, '/transcripts/12/report', {
    method: 'POST',
    headers: {
      origin: `https://${hostname}`,
      cookie: 'sma_session=demo; sma_csrf=csrf-value',
      'x-csrf-token': 'csrf-value',
      'content-type': 'application/json',
    },
    body: JSON.stringify({ transcript: 'sample' }),
  })

  expect(response.status).toBe(200)
  expect(received).toEqual({
    method: 'POST',
    url: '/transcripts/12/report',
    host: hostname,
    origin: `https://${hostname}`,
    cookie: 'sma_session=demo; sma_csrf=csrf-value',
    csrf: 'csrf-value',
    body: JSON.stringify({ transcript: 'sample' }),
  })
  expect(response.headers['set-cookie'][0]).toContain('Secure')

  const denied = await sendRequest(port, 'unlisted.example', '/health')
  expect(denied.status).toBe(403)
})
