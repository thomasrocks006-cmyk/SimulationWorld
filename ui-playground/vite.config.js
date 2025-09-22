import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    open: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path
      }
    }
  }
})
