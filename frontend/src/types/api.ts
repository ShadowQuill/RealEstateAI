/// <reference types="vite/client" />

// ==================== API 响应类型 ====================

export interface CityInfo {
  name: string;
  count: number;
  avg_price: number | null;
  min_price: number | null;
  max_price: number | null;
}

export interface HouseListing {
  id: number;
  title: string;
  city: string;
  region: string | null;
  community: string | null;
  price: number | null;
  unit_price: number | null;
  area: number | null;
  rooms: string | null;
  floor_info: string | null;
  orientation: string | null;
  decoration: string | null;
  year: number | null;
  description: string | null;
  url: string | null;
  crawled_at: string | null;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface HouseDetail extends HouseListing {
  same_community: {
    id: number;
    title: string;
    price: number | null;
    area: number | null;
    rooms: string | null;
  }[];
}

export interface CityStats {
  city: string;
  total_listings: number;
  avg_price: number | null;
  min_price: number | null;
  max_price: number | null;
  avg_unit_price: number | null;
  avg_area: number | null;
  region_distribution: { region: string; count: number }[];
  room_distribution: { rooms: string; count: number }[];
  year_distribution: { year: number; count: number }[];
}

export interface TrendPrediction {
  year: number;
  predicted_price: number;
  yoy_growth: number;
}

export interface CityTrendResult {
  city: string;
  predictions: TrendPrediction[];
  historical: { year: number; price: number; count: number }[];
  model_type: string;
  confidence: string;
}

export interface ListingFutureResult {
  city: string;
  current_price: number;
  area: number;
  predictions: TrendPrediction[];
  city_trend: CityTrendResult;
  total_growth: number;
}

export interface NLPFraudRisk {
  risk_level: string;
  hype_similarity_score: number;
  contains_high_risk_words: boolean;
  risk_reasons: string[];
}

export interface NLPSentiment {
  sentiment: string;
  positive_words_count: number;
  negative_words_count: number;
  score: number;
}

export interface NLPFeatures {
  [key: string]: string[] | number | undefined;
  area_matched?: number;
  building_year_matched?: number;
}

export interface NLPAnalysis {
  deal_price: number | null;
  unit_price: number | null;
  price_reason: string[];
  fraud_risk: NLPFraudRisk;
  regions: string[];
  features: NLPFeatures;
  sentiment: NLPSentiment;
  text_length: number;
}

export interface DashboardOverview {
  summary: {
    total_listings: number;
    cities_count: number;
    avg_price: number | null;
    avg_unit_price: number | null;
    avg_area: number | null;
  };
  city_price_ranking: { city: string; avg_price: number; count: number }[];
  decoration_distribution: { type: string; count: number }[];
  price_area_scatter: { price: number; area: number; city: string; region: string }[];
}

export interface YearlyTrend {
  yearly_trends: {
    [city: string]: { year: number; avg_price: number; count: number }[];
  };
}

export interface PredictConfig {
  cities: string[];
  layouts: string[];
  floors: string[];
  source: string;
}

// ==================== API 配置 ====================

const API_BASE = 'http://localhost:8000';

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ==================== API 函数 ====================

export const api = {
  // 城市
  getCities: () => fetchAPI<{ cities: CityInfo[]; total_cities: number }>('/api/cities'),

  // 房源列表
  getCityListings: (city: string, params?: {
    page?: number; page_size?: number; sort_by?: string; sort_order?: string;
    min_price?: number; max_price?: number; min_area?: number; max_area?: number; region?: string;
  }) => {
    const sp = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => { if (v !== undefined) sp.set(k, String(v)); });
    }
    return fetchAPI<PaginatedResponse<HouseListing>>(`/api/cities/${encodeURIComponent(city)}/listings?${sp}`);
  },

  // 城市统计
  getCityStats: (city: string) => fetchAPI<CityStats>(`/api/cities/${encodeURIComponent(city)}/stats`),

  // 房源详情
  getListingDetail: (id: number) => fetchAPI<HouseDetail>(`/api/listings/${id}`),

  // 城市趋势预测
  getCityTrend: (city: string, futureYears = 5) =>
    fetchAPI<CityTrendResult>(`/api/predict/city_trend/${encodeURIComponent(city)}?future_years=${futureYears}`),

  // 单个房源未来预测
  predictListingFuture: (city: string, currentPrice: number, area: number, futureYears = 5) =>
    fetchAPI<ListingFutureResult>('/api/predict/listing_future', {
      method: 'POST',
      body: JSON.stringify({ city, current_price: currentPrice, area, future_years: futureYears }),
    }),

  // 价格预测（给定房源特征，返回 AI 预测总价，单位：万元）
  predictPrice: (features: Record<string, number | string>) =>
    fetchAPI<{ predicted_price: number }>('/api/predict/price', {
      method: 'POST',
      body: JSON.stringify(features),
    }),

  // NLP 文本分析
  analyzeText: (text: string) =>
    fetchAPI<NLPAnalysis>('/api/analyze/text', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  // 分析房源描述
  analyzeListing: (id: number) => fetchAPI<{ listing_id: number; title: string; city: string; price: number | null; analysis: NLPAnalysis }>(`/api/analyze/listing/${id}`, { method: 'POST' }),

  // 仪表盘
  getDashboardOverview: () => fetchAPI<DashboardOverview>('/api/dashboard/overview'),
  getYearlyTrend: () => fetchAPI<YearlyTrend>('/api/dashboard/yearly_trend'),

  // 配置（避免前端硬编码城市/户型/楼层列表）
  getPredictConfig: () => fetchAPI<PredictConfig>('/api/config/predict'),
};
