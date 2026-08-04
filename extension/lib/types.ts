export type HealthResponse = {
  status: 'ok';
  service: string;
  version: string;
  authMode: 'api_key' | 'oauth';
};

export type ResearchRequest = {
  keyword: string;
  limit: number;
  enrichShops: boolean;
  maxShopLookups: number;
  sortOn: 'created' | 'score' | 'price' | 'updated';
  sortOrder: 'asc' | 'desc';
};

export type ScoreBreakdown = {
  momentum: number;
  freshness: number;
  demand: number;
  seo: number;
  shopValidation: number;
  priceFit: number;
};

export type ListingResult = {
  listingId: number;
  title: string;
  url: string;
  imageUrl: string | null;
  shopId: number | null;
  taxonomyId: number | null;
  price: number | null;
  currencyCode: string | null;
  listingAgeDays: number | null;
  numFavorers: number;
  tagCount: number;
  resultRank: number;
  shopSales: number | null;
  shopReviewCount: number | null;
  opportunityScore: number;
  dataConfidence: number;
  scoreLabel: 'High potential' | 'Promising' | 'Watch' | 'Low signal';
  scoreBreakdown: ScoreBreakdown;
};

export type ResearchResponse = {
  keyword: string;
  generatedAt: string;
  source: 'etsy_official_api';
  resultCount: number;
  authMode: 'api_key' | 'oauth';
  warnings: string[];
  items: ListingResult[];
};

export type ExtensionSettings = {
  apiBaseUrl: string;
  defaultLimit: number;
  defaultEnrichShops: boolean;
};
