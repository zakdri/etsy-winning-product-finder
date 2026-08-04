import type { ExtensionSettings } from './types';

const SETTINGS_KEY = 'trendscout.settings';

export const DEFAULT_SETTINGS: ExtensionSettings = {
  apiBaseUrl: 'http://127.0.0.1:8765',
  defaultLimit: 100,
  defaultEnrichShops: true,
};

export async function loadSettings(): Promise<ExtensionSettings> {
  const stored = await browser.storage.local.get(SETTINGS_KEY);
  const value = stored[SETTINGS_KEY] as Partial<ExtensionSettings> | undefined;
  return {
    ...DEFAULT_SETTINGS,
    ...value,
  };
}

export async function saveSettings(
  settings: ExtensionSettings,
): Promise<void> {
  await browser.storage.local.set({ [SETTINGS_KEY]: settings });
}

export async function saveLastKeyword(keyword: string): Promise<void> {
  await browser.storage.local.set({ 'trendscout.lastKeyword': keyword });
}

export async function loadLastKeyword(): Promise<string> {
  const stored = await browser.storage.local.get('trendscout.lastKeyword');
  return typeof stored['trendscout.lastKeyword'] === 'string'
    ? stored['trendscout.lastKeyword']
    : '';
}
