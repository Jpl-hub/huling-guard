import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const runtimeProxyTarget = process.env.VITE_RUNTIME_PROXY_TARGET || 'http://127.0.0.1:18014'
const runtimePrefixes = [
  '/health',
  '/meta',
  '/state',
  '/summary',
  '/timeline',
  '/incidents',
  '/system-profile',
  '/archives',
  '/demo-videos',
  '/demo-sessions',
  '/session-report',
  '/archive-session',
  '/reset',
]

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: Object.fromEntries(
      runtimePrefixes.map((prefix) => [
        prefix,
        {
          target: runtimeProxyTarget,
          changeOrigin: true,
        },
      ]),
    ),
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/@arco-design/web-vue')) {
            return 'arco'
          }
          if (id.includes('node_modules/echarts') || id.includes('node_modules/vue-echarts')) {
            return 'charts'
          }
          if (id.includes('node_modules/vue') || id.includes('node_modules/vue-router')) {
            return 'vue-core'
          }
          return undefined
        },
      },
    },
  },
})
