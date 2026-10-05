import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// En desarrollo el panel corre en 5174 y le pasa /api a FastAPI (8083)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': process.env.VITE_API_PROXY ?? 'http://localhost:8083',
    },
  },
  preview: { port: 5174 },
})
