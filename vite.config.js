import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em produção o backend (FastAPI) serve o dist/ no mesmo host, sem proxy.
// Em dev, faz proxy do /api e /socket.io para o backend local (IPv4 127.0.0.1).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:3012',
      '/socket.io': { target: 'http://127.0.0.1:3012', ws: true },
    },
  },
})
