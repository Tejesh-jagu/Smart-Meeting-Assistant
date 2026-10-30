import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const hostnamePattern = /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i

export function createViteConfig(env = {}) {
  const ngrokHostname = env.NGROK_HOSTNAME?.trim().toLowerCase()
  if (ngrokHostname && !hostnamePattern.test(ngrokHostname)) {
    throw new Error('NGROK_HOSTNAME must be an exact hostname without a scheme, path, or port.')
  }

  const apiPort = env.VITE_API_PORT?.trim() || '8000'
  if (!/^\d{1,5}$/.test(apiPort) || Number(apiPort) < 1 || Number(apiPort) > 65535) {
    throw new Error('VITE_API_PORT must be a valid local TCP port.')
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        cn: fileURLToPath(new URL('./src/utils/cn.js', import.meta.url)),
      },
    },
    server: {
      host: 'localhost',
      strictPort: true,
      allowedHosts: ngrokHostname ? [ngrokHostname] : [],
      proxy: {
        '^/(auth|transcripts|reports|health)(/|$)': {
          target: `http://127.0.0.1:${apiPort}`,
          changeOrigin: false,
        },
      },
    },
  }
}

export default defineConfig(({ mode }) => createViteConfig(loadEnv(mode, process.cwd(), '')))
