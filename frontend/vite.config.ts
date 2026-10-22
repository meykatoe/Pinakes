import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  // hls.js 已延遲載入
  build: { chunkSizeWarningLimit: 700 },
  test: { environment: 'jsdom' },
  server: {
    // 轉發後端
    proxy: { '/api': 'http://localhost:8000' },
  },
})
