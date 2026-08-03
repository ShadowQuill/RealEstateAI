import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ComposedChart, Bar
} from "recharts";
import {
  TrendingUp, ArrowLeft, MapPin, Home, DollarSign, Ruler,
  Calendar, Palette, DoorOpen, ChevronRight
} from "lucide-react";
import { api } from "@/types/api";
import type { HouseDetail, ListingFutureResult } from "@/types/api";
import { formatPrice, formatArea, formatUnitPrice, getTrendColor, getPriceRatioBadge } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ChartContainer } from "@/components/ChartContainer";

export default function ListingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [listing, setListing] = useState<HouseDetail | null>(null);
  const [prediction, setPrediction] = useState<ListingFutureResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [predicting, setPredicting] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api.getListingDetail(Number(id))
      .then(setListing)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const handlePredict = async () => {
    if (!listing || !listing.price || !listing.city) return;
    setPredicting(true);
    try {
      const result = await api.predictListingFuture(
        listing.city, listing.price, listing.area || 100, 5
      );
      setPrediction(result);
    } catch (e) {
      console.error(e);
    } finally {
      setPredicting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Skeleton className="h-64 lg:col-span-2 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!listing) {
    return (
      <div className="p-6 max-w-5xl mx-auto text-center py-20">
        <Home className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
        <h2 className="text-lg font-medium">房源未找到</h2>
        <Button variant="link" asChild className="mt-2">
          <Link to="/listings">返回房源列表</Link>
        </Button>
      </div>
    );
  }

  const chartData = prediction ? [
    { name: '当前', price: prediction.current_price, type: 'current' as const },
    ...prediction.predictions.map(p => ({ name: `${p.year}年`, price: p.predicted_price, growth: p.yoy_growth, type: 'predicted' as const })),
  ] : [];

  const totalGrowth = prediction?.total_growth || 0;
  const badge = listing.price && listing.unit_price ? getPriceRatioBadge(1) : null;

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-6">
      {/* Back */}
      <Link to="/listings" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="w-4 h-4" />
        返回房源列表
      </Link>

      {/* Listing Header */}
      <Card className="glow-card border-0 overflow-hidden">
        <CardContent className="p-6">
          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="secondary" className="gap-1"><MapPin className="w-3 h-3" />{listing.city}</Badge>
                {listing.region && <Badge variant="outline">{listing.region}</Badge>}
                {badge && <Badge className={badge.className}>{badge.label}</Badge>}
              </div>
              <h1 className="text-xl font-bold">{listing.community || listing.title}</h1>
              <p className="text-sm text-muted-foreground">{listing.title}</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-primary tracking-tight">{formatPrice(listing.price)}</p>
              <p className="text-sm text-muted-foreground">{formatUnitPrice(listing.unit_price)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Details Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {[
          { icon: Ruler, label: "面积", value: formatArea(listing.area) },
          { icon: DoorOpen, label: "户型", value: listing.rooms || '--' },
          { icon: Palette, label: "装修", value: listing.decoration || '--' },
          { icon: Calendar, label: "建成年份", value: listing.year || '--' },
          { icon: DollarSign, label: "楼层", value: listing.floor_info || '--' },
          { icon: Home, label: "朝向", value: listing.orientation || '--' },
        ].map(({ icon: Icon, label, value }) => (
          <Card key={label} className="glow-card border-0">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Icon className="w-4 h-4 text-primary" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="font-semibold text-sm">{value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Description */}
      {listing.description && (
        <Card className="glow-card border-0">
          <CardHeader>
            <CardTitle className="text-base">房源描述</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
              {listing.description}
            </p>
            <Button variant="outline" size="sm" className="mt-3 gap-1" asChild>
              <Link to={`/nlp?listing_id=${listing.id}`}>
                分析此描述 <ChevronRight className="w-3 h-3" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Prediction Section */}
      <Card className="glow-card border-0 border-l-4 border-l-primary">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="w-4 h-4 text-primary" />
                未来价格趋势预测
              </CardTitle>
              <CardDescription>基于{listing.city}历史数据的5年趋势预测</CardDescription>
            </div>
            {!prediction && (
              <Button onClick={handlePredict} disabled={predicting} className="gap-2">
                <span className="inline-flex w-4 h-4 items-center justify-center">
                  <span className={`animate-spin${predicting ? '' : ' hidden'}`}>⏳</span>
                  <TrendingUp className={`w-4 h-4${predicting ? ' hidden' : ''}`} />
                </span>
                {predicting ? '分析中...' : '开始预测'}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!prediction ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <TrendingUp className="w-12 h-12 text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground">点击「开始预测」按钮查看该房源未来5年的价格走势</p>
            </div>
          ) : (
            <div className="space-y-4" key="prediction-result">
              {/* Summary */}
              <div className="flex items-center gap-6 bg-accent/50 rounded-xl p-4">
                <div>
                  <p className="text-xs text-muted-foreground">5年总增长</p>
                  <p className={cn("text-2xl font-bold", getTrendColor(totalGrowth))}>
                    {totalGrowth > 0 ? '+' : ''}{totalGrowth}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">预测终值</p>
                  <p className="text-xl font-bold">{formatPrice(prediction.predictions[prediction.predictions.length - 1]?.predicted_price)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">当前价值</p>
                  <p className="text-xl font-bold">{formatPrice(prediction.current_price)}</p>
                </div>
              </div>

              {/* Chart */}
              <ChartContainer height={300} resetKey={chartData.length}>
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" tickFormatter={(v) => `${v}万`} />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))', background: 'hsl(var(--card))' }}
                    formatter={(value: number, name: string) => {
                      if (name === 'price') return [`${value}万`, '预测价格'];
                      if (name === 'growth') return [`${value}%`, '同比增长'];
                      return [value, name];
                    }}
                  />
                  <Bar dataKey="price" fill="hsl(var(--primary) / 0.7)" radius={[6, 6, 0, 0]} name="price" />
                  <Line type="monotone" dataKey="growth" stroke="hsl(var(--chart-4))" strokeWidth={2} dot={{ r: 4 }} name="growth" />
                </ComposedChart>
              </ChartContainer>

              {/* Yearly predictions */}
              <div className="grid grid-cols-5 gap-2">
                {prediction.predictions.map((p) => (
                  <Card key={p.year} className="border-0 bg-accent/50">
                    <CardContent className="p-3 text-center">
                      <p className="text-xs text-muted-foreground">{p.year}年</p>
                      <p className="font-bold text-sm mt-1">{formatPrice(p.predicted_price)}</p>
                      <p className={cn("text-xs mt-0.5", getTrendColor(p.yoy_growth))}>
                        {p.yoy_growth > 0 ? '+' : ''}{p.yoy_growth}%
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
