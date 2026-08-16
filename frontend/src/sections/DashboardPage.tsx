import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Building, TrendingUp, MapPin, BarChart3, ArrowRight, DollarSign, Home } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ScatterChart, Scatter, Cell } from "recharts";
import { api } from "@/types/api";
import type { CityInfo, DashboardOverview } from "@/types/api";
import { formatPrice } from "@/lib/format";
import { ChartContainer } from "@/components/ChartContainer";

export default function DashboardPage() {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [ov, cties] = await Promise.all([
          api.getDashboardOverview(),
          api.getCities(),
        ]);
        setOverview(ov);
        setCities(cties.cities);
      } catch (e) {
        console.error('Failed to load dashboard:', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-80 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      </div>
    );
  }

  const summary = overview?.summary;

  const statCards = [
    { icon: Building, label: "房源总数", value: summary?.total_listings?.toLocaleString() || '--', color: "text-primary", bg: "bg-primary/10" },
    { icon: MapPin, label: "覆盖城市", value: summary?.cities_count?.toString() || '--', color: "text-sky-500", bg: "bg-sky-500/10" },
    { icon: DollarSign, label: "均价", value: formatPrice(summary?.avg_price), color: "text-emerald-500", bg: "bg-emerald-500/10" },
    { icon: TrendingUp, label: "均价/㎡", value: summary?.avg_unit_price ? `${summary.avg_unit_price.toLocaleString()}元` : '--', color: "text-amber-500", bg: "bg-amber-500/10" },
  ];

  const barData = (overview?.city_price_ranking || []).slice(0, 10).map(c => ({
    name: c.city,
    price: Math.round(c.avg_price),
  }));

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">房产数据分析平台</h1>
          <p className="text-muted-foreground mt-1">智能化洞察房产市场趋势与价值</p>
        </div>
        <Button onClick={() => navigate('/listings')} className="gap-2">
          <Building className="w-4 h-4" />
          查看房源
          <ArrowRight className="w-4 h-4" />
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.label} className="glow-card hover-lift overflow-hidden border-0">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                  <p className="text-2xl font-bold mt-1 tracking-tight">{stat.value}</p>
                </div>
                <div className={`w-10 h-10 rounded-xl ${stat.bg} flex items-center justify-center`}>
                  <stat.icon className={`w-5 h-5 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* City Price Ranking */}
        <Card className="lg:col-span-1 glow-card border-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="w-4 h-4 text-primary" />
              城市均价排行
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ChartContainer height={320} resetKey={barData.length}>
              <BarChart data={barData} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
                <XAxis type="number" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis type="category" dataKey="name" width={50} tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))', background: 'hsl(var(--card))' }}
                  labelStyle={{ color: 'hsl(var(--card-foreground))' }}
                  itemStyle={{ color: 'hsl(var(--card-foreground))' }}
                  formatter={(value: number) => [`${value}万`, '均价']}
                />
                <Bar dataKey="price" radius={[0, 6, 6, 0]} isAnimationActive={false}>
                  {barData.map((_, idx) => (
                    <Cell key={idx} fill={`hsl(var(--primary) / ${1 - idx * 0.07})`} />
                  ))}
                </Bar>
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>

        {/* Price vs Area Scatter */}
        <Card className="lg:col-span-2 glow-card border-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <DollarSign className="w-4 h-4 text-primary" />
              价格-面积分布
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ChartContainer height={320} resetKey={overview?.price_area_scatter?.length ?? 0}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis type="number" dataKey="area" name="面积" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <YAxis type="number" dataKey="price" name="总价" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))', background: 'hsl(var(--card))' }}
                  labelStyle={{ color: 'hsl(var(--card-foreground))' }}
                  itemStyle={{ color: 'hsl(var(--card-foreground))' }}
                  formatter={(value: number, name: string) => [name === '总价' ? `${value} 万` : `${value} ㎡`, name]}
                />
                <Scatter data={overview?.price_area_scatter?.slice(0, 2000) || []} fill="hsl(var(--primary) / 0.6)" isAnimationActive={false} />
              </ScatterChart>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>

      {/* Cities Grid */}
      <Card className="glow-card border-0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <MapPin className="w-4 h-4 text-primary" />
            城市概览
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {cities.map((city) => (
              <Card
                key={city.name}
                className="cursor-pointer hover-lift border hover:border-primary/30 transition-all"
                onClick={() => navigate(`/listings?city=${encodeURIComponent(city.name)}`)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Home className="w-4 h-4 text-primary" />
                    <span className="font-semibold text-sm">{city.name}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{city.count} 套房源</p>
                  <p className="text-sm font-bold mt-1">{formatPrice(city.avg_price)}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
