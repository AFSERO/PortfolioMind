import path from 'path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// BACKEND_URL is set by Docker Compose; falls back to localhost for local dev
const BACKEND_URL = process.env.BACKEND_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',   // listen on all interfaces so Docker port mapping works
    port: 5173,
    watch: {
      usePolling: true,
    },
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
        timeout: 660000,
        proxyTimeout: 660000,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
