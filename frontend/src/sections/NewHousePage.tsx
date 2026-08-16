import { useEffect, useMemo, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ChartContainer } from "@/components/ChartContainer";
import { Landmark, Building2, Search, Info } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { api } from "@/types/api";
import type { IndexCityInfo, CityIndexSeries, IndexCompareResult } from "@/types/api";

const METRIC_LABEL = {
  commodity_idx: "新房（商品住宅）价格指数",
  secondhand_idx: "二手房价格指数",
  resident_idx: "二手住宅价格指数",
} as const;

function monthLabel(y: number, m: number) {
  return `${y}-${String(m).padStart(2, "0")}`;
}

export default function NewHousePage() {
  const [cities, setCities] = useState<IndexCityInfo[]>([]);
  const [citySearch, setCitySearch] = useState("");
  const [selected, setSelected] = useState<string>("");
  const [baseType, setBaseType] = useState<"同比" | "环比">("同比");
  const [series, setSeries] = useState<CityIndexSeries | null>(null);
  const [loadingSeries, setLoadingSeries] = useState(false);

  // 多城对比
  const [compareCities, setCompareCities] = useState<string[]>([]);
  const [compareMetric, setCompareMetric] = useState<"commodity_idx" | "secondhand_idx" | "resident_idx">("commodity_idx");
  const [compareData, setCompareData] = useState<IndexCompareResult | null>(null);
  const [loadingCompare, setLoadingCompare] = useState(false);

  useEffect(() => {
    api.getIndexCities().then(res => {
      setCities(res.cities);
      if (res.cities.length) setSelected(res.cities[0].name);
    }).catch(e => console.error(e));
  }, []);

  const filteredCities = useMemo(
    () => cities.filter(c => c.name.includes(citySearch.trim())),
    [cities, citySearch]
  );

  const loadSeries = useCallback(async (city: string, bt: "同比" | "环比") => {
    if (!city) return;
    setLoadingSeries(true);
    try {
      const data = await api.getCityIndex(city, bt);
      setSeries(data);
    } catch (e) { console.error(e); }
    finally { setLoadingSeries(false); }
  }, []);

  useEffect(() => { loadSeries(selected, baseType); }, [selected, baseType, loadSeries]);

  const chartData = useMemo(() => {
    if (!series) return [];
    return series.series.map(p => ({
      label: monthLabel(p.year, p.month),
      新房: p.commodity_idx ?? null,
      二手房: p.secondhand_idx ?? null,
    }));
  }, [series]);

  const loadCompare = useCallback(async () => {
    if (compareCities.length < 1) { setCompareData(null); return; }
    setLoadingCompare(true);
    try {
      const data = await api.getIndexCompare(compareCities, baseType, compareMetric);
      setCompareData(data);
    } catch (e) { console.error(e); }
    finally { setLoadingCompare(false); }
  }, [compareCities, baseType, compareMetric]);

  useEffect(() => { loadCompare(); }, [loadCompare]);

  const compareChartData = useMemo(() => {
    if (!compareData) return [];
    // 取各城市首个城市的月份轴，按 (year,month) 对齐
    const firstCity = compareCities.find(c => compareData.series[c]);
    if (!firstCity) return [];
    const ref = compareData.series[firstCity];
    return ref.map((pt, i) => {
      const row: Record<string, string | number | null> = {
        label: monthLabel(pt.year, pt.month),
      };
      for (const city of compareCities) {
        const arr = compareData.series[city];
        row[city] = arr && arr[i] ? arr[i].value : null;
      }
      return row;
    });
  }, [compareData, compareCities]);

  const toggleCompareCity = (city: string) => {
    setCompareCities(prev =>
      prev.includes(city) ? prev.filter(c => c !== city) : [...prev, city]
    );
  };

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Landmark className="w-6 h-6 text-primary" /> 新房价格指数
        </h1>
        <p className="text-muted-foreground mt-1">
          数据来源：国家统计局 70 城房价指数（新建商品住宅 + 二手住宅，月度，2006 至今）
        </p>
      </div>

      {/* 指数解读 */}
      <Card className="border border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Info className="w-5 h-5 text-primary" /> 怎么看懂「价格指数」？
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-base text-foreground/90">
          <p>
            价格指数不是“每平米多少钱”，而是一把衡量<span className="font-semibold">“房价涨跌了多少”</span>的尺子：
            把某个固定起点（基期）的房价设为 <span className="font-semibold text-primary">100</span>，之后只反映相对基期的变化。
          </p>

          {/* 直观刻度条 */}
          <div className="rounded-lg border bg-background/60 p-4">
            <div className="flex items-center justify-between text-sm text-muted-foreground mb-2">
              <span>比基期便宜</span>
              <span className="font-medium text-foreground">基期 = 100</span>
              <span>比基期贵</span>
            </div>
            <div className="relative h-3 rounded-full bg-gradient-to-r from-emerald-500/70 via-muted to-rose-500/70">
              <div className="absolute left-1/2 -translate-x-1/2 -top-1 w-0.5 h-5 bg-foreground/40" />
            </div>
            <div className="flex items-center justify-between text-xs text-muted-foreground mt-2">
              <span>&lt; 100（如 95 ≈ 跌 5%）</span>
              <span>&gt; 100（如 105 ≈ 涨 5%）</span>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-3 text-sm leading-relaxed">
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
              <p className="font-medium mb-1">为什么新房看指数而不是房价？</p>
              <p className="text-muted-foreground">
                新房（一手房）的挂牌/备案价常受限价、摇号、地方调控影响，不等于真实成交价，
                公开可拿到的房源级成交数据也很少。国家统计局的「新建商品住宅价格指数」基于真实网签成交编制，
                是观察新房市场最可靠的官方口径。
              </p>
            </div>
            <div className="rounded-lg border border-sky-500/20 bg-sky-500/5 p-3">
              <p className="font-medium mb-1">怎么看走势？</p>
              <p className="text-muted-foreground">
                「同比」= 和去年同月比；「环比」= 和上个月比。把「新房」与「二手房」两条线叠在一起，
                能直观看出一、二手市场的“温差”。
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* 城市选择 */}
        <Card className="glow-card border-0 h-fit">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Building2 className="w-4 h-4" /> 选择城市（{cities.length} 城）
            </CardTitle>
            <div className="relative mt-2">
              <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索城市..."
                className="pl-9 h-9"
                value={citySearch}
                onChange={e => setCitySearch(e.target.value)}
              />
            </div>
          </CardHeader>
          <CardContent className="max-h-[60vh] overflow-y-auto space-y-1">
            {filteredCities.map(c => (
              <button
                key={c.name}
                onClick={() => setSelected(c.name)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors flex items-center justify-between ${
                  selected === c.name ? "bg-primary/10 text-primary font-medium" : "hover:bg-accent"
                }`}
              >
                <span>{c.name}</span>
                <span className="text-xs text-muted-foreground">{c.min_year}–{c.max_year}</span>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* 主图：单城 新房 vs 二手房 */}
        <div className="space-y-4">
          <Card className="glow-card border-0">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-base">
                {selected} · {baseType} · 新房 vs 二手房
              </CardTitle>
              <div className="flex gap-1">
                {(["同比", "环比"] as const).map(bt => (
                  <Button
                    key={bt} size="sm" variant={baseType === bt ? "default" : "outline"}
                    onClick={() => setBaseType(bt)}
                  >
                    {bt}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {loadingSeries ? (
                <Skeleton className="h-[360px] w-full" />
              ) : (
                <ChartContainer height={360} resetKey={`${selected}-${baseType}`}>
                  <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 64 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis
                      dataKey="label" tick={{ fontSize: 10 }} minTickGap={24}
                      stroke="hsl(var(--muted-foreground))"
                      angle={-45} textAnchor="end" height={56}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" domain={['auto', 'auto']}
                      label={{ value: '价格指数（基准=100）', angle: -90, position: 'insideLeft', fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                    />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))', background: 'hsl(var(--card))' }}
                      labelStyle={{ color: 'hsl(var(--card-foreground))' }}
                      itemStyle={{ color: 'hsl(var(--card-foreground))' }}
                      formatter={(value: number, name: string) => [`${value}`, name]}
                    />
                    <Legend verticalAlign="top" height={28} />
                    <Line type="monotone" dataKey="新房" name="新建商品住宅指数" stroke="hsl(var(--primary))" dot={false} strokeWidth={2} connectNulls isAnimationActive={false} />
                    <Line type="monotone" dataKey="二手房" name="二手住宅指数" stroke="#f97316" dot={false} strokeWidth={2} connectNulls isAnimationActive={false} />
                  </LineChart>
                </ChartContainer>
              )}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-primary inline-block" /> 新建商品住宅指数</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-[#f97316] inline-block" /> 二手住宅指数</span>
              </div>
            </CardContent>
          </Card>

          {/* 多城对比 */}
          <Card className="glow-card border-0">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">多城对比</CardTitle>
              <div className="flex flex-wrap gap-2 mt-2">
                {(Object.keys(METRIC_LABEL) as (keyof typeof METRIC_LABEL)[]).map(m => (
                  <Button
                    key={m} size="sm" variant={compareMetric === m ? "default" : "outline"}
                    onClick={() => setCompareMetric(m)}
                  >
                    {METRIC_LABEL[m]}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-1.5">
                {filteredCities.slice(0, 12).map(c => (
                  <Badge
                    key={c.name}
                    variant={compareCities.includes(c.name) ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => toggleCompareCity(c.name)}
                  >
                    {c.name}
                  </Badge>
                ))}
                <span className="text-xs text-muted-foreground self-center">点击选择对比城市（含已选 {compareCities.length}）</span>
              </div>
              {loadingCompare ? (
                <Skeleton className="h-[300px] w-full" />
              ) : compareData && compareChartData.length ? (
                <ChartContainer height={300} resetKey={`${compareCities.join(',')}-${compareMetric}-${baseType}`}>
                  <LineChart data={compareChartData} margin={{ top: 10, right: 20, left: 0, bottom: 64 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} minTickGap={30}
                      stroke="hsl(var(--muted-foreground))" angle={-45} textAnchor="end" height={56} />
                    <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" domain={['auto', 'auto']}
                      label={{ value: '价格指数（基准=100）', angle: -90, position: 'insideLeft', fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
                    <Tooltip />
                    <Legend verticalAlign="top" height={28} />
                    {compareCities.map((city, i) => (
                      <Line
                        key={city} type="monotone" dataKey={city} dot={false} strokeWidth={2}
                        stroke={`hsl(${(i * 47) % 360} 70% 50%)`} connectNulls isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ChartContainer>
              ) : (
                <p className="text-sm text-muted-foreground py-10 text-center">
                  选择 1 个以上城市查看「{METRIC_LABEL[compareMetric]}」对比走势
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
