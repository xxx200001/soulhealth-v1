import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端端口只在一处配置：根目录 .env 的 SOULHEALTH_PORT（默认 8001）。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const port = env.SOULHEALTH_PORT || '8001'
  return {
    plugins: [vue()],
    server: {
      host: true,
      port: 5173,
      allowedHosts: true,
      proxy: { '/api': `http://127.0.0.1:${port}` },
    },
    build: { outDir: 'dist', emptyOutDir: true },
  }
})
