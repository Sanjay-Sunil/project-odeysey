import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/agent': 'http://localhost:8000',
      '/push': 'http://localhost:8000',
      '/refer': 'http://localhost:8000',
      '/heatmap-search': 'http://localhost:8000',
    },
  },
});
