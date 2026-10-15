import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  server: {
    // 轉發後端
    proxy: { '/api': 'http://localhost:8000' },
  },
})
