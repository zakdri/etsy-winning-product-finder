import { useEffect, useState } from 'react';
import { Icon } from '../../components/Icon';
import { getHealth } from '../../lib/api';
import { loadLastKeyword, loadSettings } from '../../lib/settings';

export default function App() {
  const [online, setOnline] = useState(false);
  const [status, setStatus] = useState('Checking local API…');
  const [keyword, setKeyword] = useState('');

  useEffect(() => {
    void (async () => {
      const settings = await loadSettings();
      setKeyword(await loadLastKeyword());
      try {
        const health = await getHealth(settings.apiBaseUrl);
        setOnline(true);
        setStatus(`${health.service} is ready`);
      } catch {
        setOnline(false);
        setStatus('Start the local API to research products');
      }
    })();
  }, []);

  async function openDashboard(): Promise<void> {
    const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : '';
    await browser.tabs.create({ url: browser.runtime.getURL(`/dashboard.html${query}`) });
    window.close();
  }

  return (
    <main className="popup">
      <section className="panel popup-card">
        <div className="brand"><img src="/icon.svg" alt="" /><div>TrendScout<small>Seller intelligence</small></div></div>
        <h2>Research products with clearer signals.</h2>
        <p className="subtitle">Official Etsy API data, transparent scoring, and no secret credentials inside your browser.</p>
        <div className={`status-pill ${online ? 'online' : ''}`} style={{ marginTop: 16 }}><span className="status-dot" />{status}</div>
        <button className="btn btn-primary" onClick={() => void openDashboard()}><Icon name="sparkles" />Open research dashboard</button>
        <div className="quick-list">
          <div className="quick-item"><span>Browser support</span><strong>Chrome · Edge · Firefox</strong></div>
          <div className="quick-item"><span>Data source</span><strong>Official API</strong></div>
          <div className="quick-item"><span>Credential storage</span><strong>Local backend</strong></div>
        </div>
      </section>
    </main>
  );
}
