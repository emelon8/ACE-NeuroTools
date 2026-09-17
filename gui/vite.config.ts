import { defineConfig } from 'vite';
export default defineConfig({
  base: './',
  build: { target: 'es2022' },
  server: { strictPort: true, proxy: { '/api': 'http://127.0.0.1:8765' } },
});
