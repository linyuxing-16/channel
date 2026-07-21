import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  assetsInclude: ['**/*.moc3', '**/*.physics3', '**/*.pose3', '**/*.cdi3', '**/*.exp3'],
  build: {
    target: 'es2020',
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
})
