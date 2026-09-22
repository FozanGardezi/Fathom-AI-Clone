import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The app talks to the API through the relative path /api. In dev that is
// proxied to the Django server; in the container it is proxied by nginx.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    host: true, // listen on 0.0.0.0 so the dev container is reachable
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: { port: 3000, host: true },
})
