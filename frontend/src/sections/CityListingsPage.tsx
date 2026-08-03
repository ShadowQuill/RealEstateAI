import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Search, Building, MapPin, SlidersHorizontal, ChevronLeft, ChevronRight,
  ArrowRight
} from "lucide-react";
import { api } from "@/types/api";
import type { CityStats, HouseListing, PaginatedResponse } from "@/types/api";
import { formatPrice, formatArea, formatUnitPrice } from "@/lib/format";

export default function CityListingsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  
  const selectedCity = searchParams.get("city") || "";
  const [cities, setCities] = useState<string[]>([]);
  const [listings, setListings] = useState<PaginatedResponse<HouseListing> | null>(null);
  const [stats, setStats] = useState<CityStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // Filters
  const [priceRange, setPriceRange] = useState([0, 5000]);
  const [areaRange, setAreaRange] = useState([0, 500]);
  const [region, setRegion] = useState("");
  const [sortBy, setSortBy] = useState("price");
  const [sortOrder, setSortOrder] = useState("desc");

  const page = parseInt(searchParams.get("page") || "1");
  const pageSize = 20;

  useEffect(() => {
    api.getCities().then(res => setCities(res.cities.map(c => c.name)));
  }, []);

  const loadListings = useCallback(async () => {
    if (!selectedCity) return;
    setLoading(true);
    try {
      const [listData, statsData] = await Promise.all([
        api.getCityListings(selectedCity, {
          page, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder,
          min_price: priceRange[0] > 0 ? priceRange[0] : undefined,
          max_price: priceRange[1] < 5000 ? priceRange[1] : undefined,
          min_area: areaRange[0] > 0 ? areaRange[0] : undefined,
          max_area: areaRange[1] < 500 ? areaRange[1] : undefined,
          region: region || undefined,
        }),
        api.getCityStats(selectedCity),
      ]);
      setListings(listData);
      setStats(statsData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [selectedCity, page, sortBy, sortOrder, priceRange, areaRange, region]);

  useEffect(() => {
    loadListings();
  }, [loadListings]);

  const handleCitySelect = (city: string) => {
    setSearchParams({ city, page: "1" });
  };

  const handlePageChange = (newPage: number) => {
    const params = new URLSearchParams(searchParams);
    params.set("page", String(newPage));
    setSearchParams(params);
  };

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('desc');
    }
  };

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">城市房源</h1>
        <p className="text-muted-foreground mt-1">浏览并选择房源，查看详细信息和未来价格预测</p>
      </div>

      {/* City Selector */}
      <div className="flex flex-wrap gap-2">
        {cities.map(city => (
          <Button
            key={city}
            variant={selectedCity === city ? "default" : "outline"}
            size="sm"
            onClick={() => handleCitySelect(city)}
            className="gap-2"
          >
            <Building className="w-3.5 h-3.5" />
            {city}
          </Button>
        ))}
      </div>

      {!selectedCity ? (
        <Card className="glow-card border-0">
          <CardContent className="flex flex-col items-center justify-center py-20 text-center">
            <MapPin className="w-16 h-16 text-muted-foreground/30 mb-4" />
            <h2 className="text-lg font-medium text-muted-foreground">请选择一个城市开始浏览房源</h2>
            <p className="text-sm text-muted-foreground mt-1">选择城市后将展示该城市的全部房源数据</p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Stats Bar */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { label: "房源总数", value: stats.total_listings },
                { label: "均价", value: stats.avg_price ? `${(stats.avg_price).toFixed(0)}万` : '--' },
                { label: "单价", value: stats.avg_unit_price ? `${stats.avg_unit_price.toLocaleString()}元/㎡` : '--' },
                { label: "均价面积", value: formatArea(stats.avg_area) },
                { label: "价格区间", value: `${formatPrice(stats.min_price)} - ${formatPrice(stats.max_price)}` },
              ].map(s => (
                <Card key={s.label} className="glow-card border-0">
                  <CardContent className="p-4 text-center">
                    <p className="text-xs text-muted-foreground">{s.label}</p>
                    <p className="text-lg font-bold mt-1">{String(s.value)}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Filters & Search */}
          <div className="flex items-center gap-2 flex-wrap">
            <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)} className="gap-2">
              <SlidersHorizontal className="w-3.5 h-3.5" />
              筛选
            </Button>
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索区域..."
                className="pl-9 h-9"
                value={region}
                onChange={e => setRegion(e.target.value)}
              />
            </div>
          </div>

          {showFilters && (
            <Card className="border">
              <CardContent className="p-4 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="text-sm font-medium mb-2 block">价格范围 (万): {priceRange[0]} - {priceRange[1]}</label>
                    <Slider min={0} max={5000} step={10} value={priceRange} onValueChange={setPriceRange} />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">面积范围 (㎡): {areaRange[0]} - {areaRange[1]}</label>
                    <Slider min={0} max={500} step={5} value={areaRange} onValueChange={setAreaRange} />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={loadListings}>应用筛选</Button>
                  <Button size="sm" variant="outline" onClick={() => { setPriceRange([0, 5000]); setAreaRange([0, 500]); setRegion(""); }}>
                    重置
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Table */}
          <Card className="glow-card border-0 overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px]">#</TableHead>
                    <TableHead>小区/标题</TableHead>
                    <TableHead>区域</TableHead>
                    <TableHead className="cursor-pointer select-none" onClick={() => handleSort('price')}>
                      总价 {sortBy === 'price' && (sortOrder === 'desc' ? '↓' : '↑')}
                    </TableHead>
                    <TableHead className="cursor-pointer select-none" onClick={() => handleSort('unit_price')}>
                      单价 {sortBy === 'unit_price' && (sortOrder === 'desc' ? '↓' : '↑')}
                    </TableHead>
                    <TableHead className="cursor-pointer select-none" onClick={() => handleSort('area')}>
                      面积 {sortBy === 'area' && (sortOrder === 'desc' ? '↓' : '↑')}
                    </TableHead>
                    <TableHead>户型</TableHead>
                    <TableHead>年代</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    [...Array(5)].map((_, i) => (
                      <TableRow key={i}>
                        {[...Array(9)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                      </TableRow>
                    ))
                  ) : listings?.data.map((h, idx) => (
                    <TableRow key={h.id} className="cursor-pointer hover:bg-accent/50 transition-colors">
                      <TableCell className="text-muted-foreground">{(page - 1) * pageSize + idx + 1}</TableCell>
                      <TableCell>
                        <div className="max-w-[200px]">
                          <p className="font-medium text-sm truncate">{h.community || h.title}</p>
                          <p className="text-xs text-muted-foreground truncate">{h.title}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">{h.region || '--'}</Badge>
                      </TableCell>
                      <TableCell className="font-semibold tabular-nums">{formatPrice(h.price)}</TableCell>
                      <TableCell className="tabular-nums text-sm">{formatUnitPrice(h.unit_price)}</TableCell>
                      <TableCell className="tabular-nums">{formatArea(h.area)}</TableCell>
                      <TableCell className="text-sm">{h.rooms || '--'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{h.year || '--'}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="gap-1 text-primary"
                          onClick={() => navigate(`/predict/${h.id}`)}
                        >
                          走势 <ArrowRight className="w-3 h-3" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Pagination */}
            {listings && listings.total_pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t">
                <p className="text-sm text-muted-foreground">
                  共 {listings.total} 条，第 {listings.page}/{listings.total_pages} 页
                </p>
                <div className="flex gap-1">
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => handlePageChange(page - 1)}>
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  {Array.from({ length: Math.min(5, listings.total_pages) }, (_, i) => {
                    let p: number;
                    if (listings.total_pages <= 5) {
                      p = i + 1;
                    } else if (page <= 3) {
                      p = i + 1;
                    } else if (page >= listings.total_pages - 2) {
                      p = listings.total_pages - 4 + i;
                    } else {
                      p = page - 2 + i;
                    }
                    return (
                      <Button key={p} size="sm" variant={p === page ? "default" : "outline"} onClick={() => handlePageChange(p)}>
                        {p}
                      </Button>
                    );
                  })}
                  <Button size="sm" variant="outline" disabled={page >= listings.total_pages} onClick={() => handlePageChange(page + 1)}>
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
