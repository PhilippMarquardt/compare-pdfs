import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { TanStackRouterVite } from '@tanstack/router-plugin/vite'

export default defineConfig({
  plugins: [
    TanStackRouterVite({
      target: 'react',
      autoCodeSplitting: true,
    }),
    react(),
    tailwindcss(),
  ],
  server: {
    host: true,
    port: 30097,
    proxy: {
      '/api': {
        target: 'http://localhost:30099',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    include: ['pdfjs-dist'],
  },
})
