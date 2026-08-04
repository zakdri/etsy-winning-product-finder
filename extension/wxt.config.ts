import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react', '@wxt-dev/auto-icons'],
  srcDir: '.',
  outDir: '.output',
  manifest: ({ browser }) => ({
    name: 'TrendScout – Etsy Product Research',
    short_name: 'TrendScout',
    description: 'Research Etsy listings with authorized API data, momentum signals, and transparent scoring.',
    version: '0.1.0',
    permissions: ['storage', 'tabs'],
    host_permissions: ['http://127.0.0.1/*', 'http://localhost/*'],
    action: {
      default_title: 'Open TrendScout',
    },
    browser_specific_settings:
      browser === 'firefox'
        ? {
            gecko: {
              id: 'trendscout@octopact.com',
              strict_min_version: '121.0',
            },
          }
        : undefined,
  }),
});
