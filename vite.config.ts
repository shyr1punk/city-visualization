import { sites } from '@openai/sites-vite-plugin';
import tailwindcss from '@tailwindcss/postcss';
import vinext from 'vinext';
import { defineConfig } from 'vite';
const repository = process.env.GITHUB_REPOSITORY?.split('/').at(-1);
const base =
  process.env.GITHUB_ACTIONS === 'true' && repository ? `/${repository}/` : '/';
export default defineConfig({
  base,
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
