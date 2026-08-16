export function formatPrice(price: number | null | undefined): string {
  if (price == null) return '--';
  // 房源价格字段统一以「万元」为单位存储（House.price）。
  // 超过 1 万万（即 1 亿元）时换算为「亿」，避免位数过长；
  // 否则直接以「万」为单位展示，并去掉多余的 .0。
  if (price >= 10000) return `${(price / 10000).toFixed(2)}亿`;
  return `${parseFloat(price.toFixed(1))}万`;
}

export function formatUnitPrice(price: number | null | undefined): string {
  if (price == null) return '--';
  return `${price.toLocaleString()}元/㎡`;
}

export function formatArea(area: number | null | undefined): string {
  if (area == null) return '--';
  return `${area.toFixed(1)}㎡`;
}

export function getTrendColor(growth: number): string {
  if (growth > 0) return 'text-emerald-500';
  if (growth < 0) return 'text-red-500';
  return 'text-muted-foreground';
}

export function getTrendIconClass(growth: number): string {
  if (growth > 0) return 'inline rotate-[-90deg]';
  if (growth < 0) return 'inline rotate-90';
  return '';
}

export function getPriceRatioBadge(ratio: number): { label: string; className: string } {
  if (ratio < 0.8) return { label: '低于均价', className: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' };
  if (ratio > 1.2) return { label: '高于均价', className: 'bg-amber-500/10 text-amber-500 border-amber-500/20' };
  return { label: '接近均价', className: 'bg-blue-500/10 text-blue-500 border-blue-500/20' };
}
