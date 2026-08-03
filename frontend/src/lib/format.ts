export function formatPrice(price: number | null | undefined): string {
  if (price == null) return '--';
  return price >= 10000 ? `${(price / 10000).toFixed(1)}万` : `${price.toFixed(0)}`;
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
