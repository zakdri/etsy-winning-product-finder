import { useEffect, useMemo, useState } from 'react';
import { Icon } from '../../components/Icon';
import { getHealth, runResearch } from '../../lib/api';
import {
  DEFAULT_SETTINGS,
  loadLastKeyword,
  loadSettings,
  saveLastKeyword,
  saveSettings,
} from '../../lib/settings';
import type {
  ExtensionSettings,
  ListingResult,
  ResearchResponse,
} from '../../lib/types';

type View = 'research' | 'settings';
type SortKey = 'opportunity' | 'newest' | 'favorites' | 'shopSales';

function money(value: number | null, currency: string | null): string {
  if (value === null) return '—';
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency || ''}`.trim();
  }
}

function age(value: number | null): string {
  if (value === null) return 'Unknown age';
  if (value < 1) return 'New today';
  if (value < 30) return `${Math.round(value)} days old`;
  if (value < 365) return `${Math.round(value / 30)} months old`;
  return `${(value / 365).toFixed(1)} years old`;
}

function downloadCsv(items: ListingResult[], keyword: string): void {
  const headers = [
    'listing_id', 'title', 'url', 'price', 'currency', 'age_days', 'favorites',
    'shop_sales', 'opportunity_score', 'confidence', 'label',
  ];
  const quote = (value: unknown) => `"${String(value ?? '').replaceAll('"', '""')}"`;
  const rows = items.map((item) => [
    item.listingId, item.title, item.url, item.price, item.currencyCode,
    item.listingAgeDays, item.numFavorers, item.shopSales,
    item.opportunityScore, item.dataConfidence, item.scoreLabel,
  ].map(quote).join(','));
  const blob = new Blob([[headers.join(','), ...rows].join('\n')], {
    type: 'text/csv;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${keyword.trim().replace(/[^a-z0-9]+/gi, '-').toLowerCase()}-research.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function Logo() {
  return (
    <div className="brand">
      <img src="/icon.svg" alt="" />
      <div className="brand-copy">
        TrendScout
        <small>Seller intelligence</small>
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState<View>('research');
  const [settings, setSettingsState] = useState<ExtensionSettings>(DEFAULT_SETTINGS);
  const [keyword, setKeyword] = useState('');
  const [limit, setLimit] = useState(100);
  const [enrichShops, setEnrichShops] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('opportunity');
  const [data, setData] = useState<ResearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [online, setOnline] = useState(false);
  const [healthText, setHealthText] = useState('Checking local API…');

  useEffect(() => {
    void (async () => {
      const loaded = await loadSettings();
      setSettingsState(loaded);
      setLimit(loaded.defaultLimit);
      setEnrichShops(loaded.defaultEnrichShops);
      const queryKeyword = new URLSearchParams(location.search).get('keyword');
      setKeyword(queryKeyword || (await loadLastKeyword()));
      try {
        const health = await getHealth(loaded.apiBaseUrl);
        setOnline(true);
        setHealthText(`${health.service} · ${health.authMode.replace('_', ' ')}`);
      } catch {
        setOnline(false);
        setHealthText('Local API offline');
      }
    })();
  }, []);

  const sortedItems = useMemo(() => {
    const items = [...(data?.items ?? [])];
    return items.sort((a, b) => {
      if (sortKey === 'newest') return (a.listingAgeDays ?? 999999) - (b.listingAgeDays ?? 999999);
      if (sortKey === 'favorites') return b.numFavorers - a.numFavorers;
      if (sortKey === 'shopSales') return (b.shopSales ?? -1) - (a.shopSales ?? -1);
      return b.opportunityScore - a.opportunityScore;
    });
  }, [data, sortKey]);

  const metrics = useMemo(() => {
    if (!data?.items.length) return null;
    const high = data.items.filter((item) => item.opportunityScore >= 75).length;
    const avg = data.items.reduce((sum, item) => sum + item.opportunityScore, 0) / data.items.length;
    const newest = Math.min(...data.items.map((item) => item.listingAgeDays ?? 999999));
    const confidence = data.items.reduce((sum, item) => sum + item.dataConfidence, 0) / data.items.length;
    return { high, avg, newest, confidence };
  }, [data]);

  async function research(): Promise<void> {
    const cleanKeyword = keyword.trim();
    if (cleanKeyword.length < 2) {
      setError('Enter a keyword with at least two characters.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await saveLastKeyword(cleanKeyword);
      const response = await runResearch(settings.apiBaseUrl, {
        keyword: cleanKeyword,
        limit,
        enrichShops,
        maxShopLookups: enrichShops ? Math.min(limit, 100) : 0,
        sortOn: 'created',
        sortOrder: 'desc',
      });
      setData(response);
      setOnline(true);
      setHealthText(`Official API · ${response.authMode.replace('_', ' ')}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Research failed.');
      setOnline(false);
      setHealthText('Local API offline');
    } finally {
      setLoading(false);
    }
  }

  async function persistSettings(): Promise<void> {
    const normalized = {
      ...settings,
      apiBaseUrl: settings.apiBaseUrl.trim().replace(/\/+$/, ''),
    };
    await saveSettings(normalized);
    setSettingsState(normalized);
    setLimit(normalized.defaultLimit);
    setEnrichShops(normalized.defaultEnrichShops);
    setHealthText('Checking local API…');
    try {
      const health = await getHealth(normalized.apiBaseUrl);
      setOnline(true);
      setHealthText(`${health.service} · ${health.authMode.replace('_', ' ')}`);
      setError(null);
    } catch {
      setOnline(false);
      setHealthText('Saved, but API is offline');
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <Logo />
        <nav className="nav" aria-label="Primary navigation">
          <button className={`nav-item ${view === 'research' ? 'active' : ''}`} onClick={() => setView('research')}>
            <Icon name="search" /><span>Product research</span>
          </button>
          <button className={`nav-item ${view === 'settings' ? 'active' : ''}`} onClick={() => setView('settings')}>
            <Icon name="settings" /><span>Settings</span>
          </button>
        </nav>
        <div className="sidebar-foot">
          <strong>Privacy by design</strong><br />
          Etsy credentials stay in your local API. The extension receives research results only.
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">Official API research</div>
            <h1>{view === 'research' ? 'Find early product momentum.' : 'Extension settings.'}</h1>
            <p className="subtitle">
              {view === 'research'
                ? 'Compare fresh listings using transparent signals—not invented sales estimates.'
                : 'Configure the secure local service used by every supported browser.'}
            </p>
          </div>
          <div className={`status-pill ${online ? 'online' : ''}`}>
            <span className="status-dot" />{healthText}
          </div>
        </header>

        {view === 'settings' ? (
          <section className="panel settings-grid">
            <div className="field">
              <label htmlFor="api-url">Local API URL</label>
              <input id="api-url" className="input" value={settings.apiBaseUrl} onChange={(event) => setSettingsState({ ...settings, apiBaseUrl: event.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="default-limit">Default result limit</label>
              <select id="default-limit" className="select" value={settings.defaultLimit} onChange={(event) => setSettingsState({ ...settings, defaultLimit: Number(event.target.value) })}>
                <option value={25}>25 listings</option><option value={50}>50 listings</option><option value={100}>100 listings</option>
              </select>
            </div>
            <label className="quick-item">
              <span>Enrich shop metrics by default</span>
              <input type="checkbox" checked={settings.defaultEnrichShops} onChange={(event) => setSettingsState({ ...settings, defaultEnrichShops: event.target.checked })} />
            </label>
            <button className="btn btn-primary" onClick={() => void persistSettings()}>Save and test connection</button>
            <div className="notice">
              Never place your Etsy keystring, shared secret, or OAuth token inside the extension. Store them only in the backend <code>.env</code> file.
            </div>
          </section>
        ) : (
          <>
            <section className="panel search-panel" aria-label="Product research controls">
              <div className="field">
                <label htmlFor="keyword">Keyword or niche</label>
                <input id="keyword" className="input" placeholder="e.g. vintage horse wall art" value={keyword} onChange={(event) => setKeyword(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void research(); }} />
              </div>
              <div className="field">
                <label htmlFor="limit">Listings</label>
                <select id="limit" className="select" value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
                  <option value={25}>25</option><option value={50}>50</option><option value={100}>100</option>
                </select>
              </div>
              <label className="quick-item" style={{ minHeight: 46 }}>
                <span>Shop data</span>
                <input type="checkbox" checked={enrichShops} onChange={(event) => setEnrichShops(event.target.checked)} />
              </label>
              <button className="btn btn-primary" disabled={loading} onClick={() => void research()}>
                {loading ? <><span className="spinner" />Researching</> : <><Icon name="sparkles" />Run research</>}
              </button>
            </section>

            {error && <div className="notice error">{error}</div>}
            {data?.warnings.map((warning) => <div className="notice" key={warning}>{warning}</div>)}

            {metrics && (
              <section className="metrics" aria-label="Research summary">
                <div className="metric"><div className="metric-label">High potential</div><div className="metric-value">{metrics.high}</div><div className="metric-foot">Score of 75 or higher</div></div>
                <div className="metric"><div className="metric-label">Average score</div><div className="metric-value">{metrics.avg.toFixed(0)}</div><div className="metric-foot">Across {data?.resultCount} listings</div></div>
                <div className="metric"><div className="metric-label">Newest listing</div><div className="metric-value">{metrics.newest >= 999999 ? '—' : `${Math.max(0, Math.round(metrics.newest))}d`}</div><div className="metric-foot">Freshness discovery</div></div>
                <div className="metric"><div className="metric-label">Data confidence</div><div className="metric-value">{metrics.confidence.toFixed(0)}%</div><div className="metric-foot">Field completeness</div></div>
              </section>
            )}

            <div className="toolbar">
              <div className="toolbar-left">
                <div className="segment" aria-label="Sort results">
                  {([['opportunity','Best score'],['newest','Newest'],['favorites','Favorites'],['shopSales','Shop sales']] as const).map(([key,label]) => (
                    <button key={key} className={sortKey === key ? 'active' : ''} onClick={() => setSortKey(key)}>{label}</button>
                  ))}
                </div>
              </div>
              <div className="toolbar-right">
                <button className="btn btn-ghost" disabled={!sortedItems.length} onClick={() => downloadCsv(sortedItems, keyword)}><Icon name="download" />Export CSV</button>
              </div>
            </div>

            <section className="panel results">
              {!data ? (
                <div className="empty"><strong>Start with a focused niche.</strong>Research up to 100 authorized Etsy listings and compare their opportunity signals.</div>
              ) : !sortedItems.length ? (
                <div className="empty"><strong>No listings found.</strong>Try a broader or differently phrased keyword.</div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Product</th><th>Opportunity</th><th>Price</th><th>Favorites</th><th>Shop proof</th><th>Confidence</th><th /></tr></thead>
                    <tbody>
                      {sortedItems.map((item) => (
                        <tr key={item.listingId}>
                          <td><div className="product"><img className="thumb" src={item.imageUrl || '/icon.svg'} alt="" /><div><div className="product-title" title={item.title}>{item.title}</div><div className="product-meta">#{item.resultRank} · {age(item.listingAgeDays)}</div></div></div></td>
                          <td><div className="score"><div className="score-ring" style={{ '--score': item.opportunityScore } as React.CSSProperties}><span>{item.opportunityScore}</span></div><span className={`badge ${item.opportunityScore >= 75 ? 'good' : ''}`}>{item.scoreLabel}</span></div></td>
                          <td>{money(item.price, item.currencyCode)}</td>
                          <td>{item.numFavorers.toLocaleString()}</td>
                          <td>{item.shopSales === null ? <span className="muted">Not enriched</span> : `${item.shopSales.toLocaleString()} sales`}</td>
                          <td>{item.dataConfidence}%</td>
                          <td><a className="btn btn-ghost" href={item.url} target="_blank" rel="noreferrer" aria-label={`Open ${item.title} on Etsy`}><Icon name="external" /></a></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
