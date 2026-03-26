import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/game': 'http://localhost:8091',
      '/ws': {
        target: 'ws://localhost:8091',
        ws: true,
      },
    },
  },
})
