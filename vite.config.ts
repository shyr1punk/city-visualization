import { sites } from '@openai/sites-vite-plugin';
import tailwindcss from '@tailwindcss/postcss';
import vinext from 'vinext';
import { defineConfig } from 'vite';
export default defineConfig({
  css: { postcss: { plugins: [tailwindcss()] } },
  optimizeDeps: { exclude: ['maplibre-gl'] },
  server: {
    watch: {
      useFsEvents: false,
      usePolling: true,
      ignored: ['**/data/raw/**', '**/out/**'],
    },
  },
  plugins: [vinext(), sites()],
});
