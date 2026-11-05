import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// base './' keeps every asset path relative, so dist/ works from any static host or subfolder.
export default defineConfig({
  base: './',
  plugins: [svelte()],
  server: { port: 5178 },
});
