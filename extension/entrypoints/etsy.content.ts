export default defineContentScript({
  matches: ['https://www.etsy.com/search*', 'https://www.etsy.com/*/search*'],
  runAt: 'document_idle',
  main() {
    if (document.getElementById('trendscout-launcher')) return;

    const host = document.createElement('div');
    host.id = 'trendscout-launcher';
    host.style.position = 'fixed';
    host.style.right = '20px';
    host.style.bottom = '20px';
    host.style.zIndex = '2147483647';
    const shadow = host.attachShadow({ mode: 'open' });
    const button = document.createElement('button');
    button.type = 'button';
    button.innerHTML = '<span aria-hidden="true">✦</span><span>Research this niche</span>';
    button.setAttribute('aria-label', 'Open this Etsy search in TrendScout');
    button.style.cssText = [
      'display:flex', 'align-items:center', 'gap:9px', 'border:1px solid rgba(255,255,255,.2)',
      'border-radius:999px', 'padding:12px 16px', 'background:linear-gradient(135deg,#8a6cff,#6f4eff)',
      'color:white', 'font:700 13px Inter,system-ui,sans-serif', 'box-shadow:0 16px 40px rgba(37,25,90,.35)',
      'cursor:pointer', 'transition:transform .18s ease,filter .18s ease',
    ].join(';');
    button.addEventListener('mouseenter', () => { button.style.transform = 'translateY(-2px)'; });
    button.addEventListener('mouseleave', () => { button.style.transform = 'translateY(0)'; });
    button.addEventListener('click', async () => {
      const params = new URLSearchParams(location.search);
      const keyword = params.get('q') || params.get('search_query') || '';
      if (keyword) await browser.storage.local.set({ 'trendscout.lastKeyword': keyword });
      const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : '';
      await browser.runtime.sendMessage({ type: 'OPEN_TRENDSCOUT', query });
    });
    shadow.append(button);
    document.documentElement.append(host);
  },
});
