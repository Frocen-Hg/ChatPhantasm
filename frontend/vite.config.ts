import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // ws: true 让开发模式下 /api/v1/ws 的 WebSocket 升级也走代理
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, ws: true }
    }
  }
})