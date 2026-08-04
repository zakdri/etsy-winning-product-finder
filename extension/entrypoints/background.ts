export default defineBackground(() => {
  browser.runtime.onInstalled.addListener(async ({ reason }) => {
    if (reason === 'install') {
      await browser.storage.local.set({
        'trendscout.settings': {
          apiBaseUrl: 'http://127.0.0.1:8765',
          defaultLimit: 100,
          defaultEnrichShops: true,
        },
      });
    }
  });

  browser.runtime.onMessage.addListener((message: unknown) => {
    if (!message || typeof message !== 'object') return undefined;
    const typed = message as { type?: string; query?: string };
    if (typed.type !== 'OPEN_TRENDSCOUT') return undefined;
    return browser.tabs.create({
      url: browser.runtime.getURL(`/dashboard.html${typed.query || ''}`),
    });
  });
});
