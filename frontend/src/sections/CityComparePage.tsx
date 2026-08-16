import { useState, useEffect, useMemo } from "react";
import { Building2, BarChart3, ArrowUpDown, Info, HelpCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ChartContainer } from "@/components/ChartContainer";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ReferenceLine, LabelList } from "recharts";
import { api } from "@/types/api";
import type { CityIndexSummary } from "@/types/api";

type MetricKey = "commodity_yoy" | "secondhand_yoy" | "commodity_mom" | "secondhand_mom";

const METRICS: { key: MetricKey; label: string }[] = [
  { key: "commodity_yoy", label: "新房指数·同比" },
  { key: "secondhand_yoy", label: "二手房指数·同比" },
  { key: "commodity_mom", label: "新房指数·环比" },
  { key: "secondhand_mom", label: "二手房指数·环比" },
];

export default function CityComparePage() {
  const [data, setData] = useState<CityIndexSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [metric, setMetric] = useState<MetricKey>("commodity_yoy");
  const [sortKey, setSortKey] = useState<keyof CityIndexSummary>("commodity_yoy");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    api.getCitiesSummary()
      .then(res => setData(res.cities))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const chartData = useMemo(
    () => data.map(d => ({ name: d.city, value: d[metric] ?? 0 })),
    [data, metric]
  );

  const sorted = useMemo(() => {
    const arr = [...data];
    arr.sort((a, b) => {
      const av = (a[sortKey] as number) ?? -Infinity;
      const bv = (b[sortKey] as number) ?? -Infinity;
      return sortAsc ? av - bv : bv - av;
    });
    return arr;
  }, [data, sortKey, sortAsc]);

  const toggleSort = (key: keyof CityIndexSummary) => {
    if (key === sortKey) setSortAsc(s => !s);
    else { setSortKey(key); setSortAsc(false); }
  };

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Building2 className="w-5 h-5 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight">多城房价指数对比</h1>
        </div>
        <p className="text-muted-foreground">
          横向对比各城市国家统计局房价指数（基期=100，&gt;100 表示较基期上涨、&lt;100 表示下跌）。
        </p>
      </div>

      {/* 新手说明：怎么看懂这张图 */}
      <Card className="glow-card border-0 bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Info className="w-5 h-5 text-primary" /> 怎么看懂这张对比图？
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm leading-relaxed text-foreground/90">
          <div className="rounded-lg border bg-background/60 p-3">
            <p className="font-medium mb-1">① 价格指数 ≠ 每平米单价</p>
            <p className="text-muted-foreground">
              它是一把「涨跌尺子」：把某个固定起点（基期）设为 <span className="font-semibold text-primary">100</span>，之后只反映相对基期的变化。
              所以看的是「涨了还是跌了」，不是「多少钱一平」。
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div className="rounded-lg border border-sky-500/20 bg-sky-500/5 p-3">
              <p className="font-medium mb-1">新房 vs 二手房</p>
              <p className="text-muted-foreground">「新房指数」看一手房市场，「二手房指数」看存量房（业主之间买卖）市场，两者常出现「温差」。</p>
            </div>
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
              <p className="font-medium mb-1">同比 vs 环比</p>
              <p className="text-muted-foreground">
                <span className="font-medium">同比</span> = 和去年同月比，看大趋势；<span className="font-medium">环比</span> = 和上个月比，看短期变化。
              </p>
            </div>
          </div>

          <div className="rounded-lg border bg-background/60 p-3">
            <p className="font-medium mb-1">② 颜色与基准线</p>
            <p className="text-muted-foreground">
              虚线 <span className="font-semibold">100</span> 是「涨跌分界」：柱子 <span className="text-emerald-500 font-medium">绿色（≥100）</span> 代表较基期上涨、<span className="text-red-500 font-medium">红色（&lt;100）</span> 代表下跌。
              「排名」按当前所选指标从高到低排。
            </p>
          </div>

          <div className="rounded-lg border border-primary/20 bg-primary/5 p-3">
            <p className="font-medium mb-1 flex items-center gap-1">
              <HelpCircle className="w-4 h-4 text-primary" /> 为什么只看到这「部分」城市？
            </p>
            <p className="text-muted-foreground">
              数据来自 <span className="font-medium">国家统计局「70 个大中城市」房价指数</span>——这是一个固定的 70 城样本（一线 / 二线 / 三线代表城市），并不是全国所有城市。
              所以页面覆盖的就是这 70 城，并非遗漏。这 70 城会<span className="font-medium">全部列出</span>：上方柱状图可下滑查看每一根（都按涨/跌上色），下方表格是完整清单与精确数值。若某城某指标暂无数据，会以「--」显示。
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 指标选择 + 柱状图 */}
      <Card className="glow-card border-0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="w-4 h-4 text-primary" />
            城市对比图
          </CardTitle>
          <CardDescription>选择对比指标，柱越高代表该指标数值越大。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {METRICS.map(m => (
              <button
                key={m.key}
                onClick={() => setMetric(m.key)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  metric === m.key
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-accent/50 border-border/60 hover:border-primary/50"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground py-12 text-center">加载中...</p>
          ) : (
            <ChartContainer height={Math.max(360, data.length * 22)} resetKey={`${metric}-${data.length}`}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 56 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))"
                  domain={[ (min: number) => Math.floor(min - 2), (max: number) => Math.ceil(max + 2) ]}
                />
                <YAxis
                  type="category" dataKey="name" width={76}
                  interval={0}
                  tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))"
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))', background: 'hsl(var(--card))' }}
                  labelStyle={{ color: 'hsl(var(--card-foreground))' }}
                  itemStyle={{ color: 'hsl(var(--card-foreground))' }}
                  formatter={(value: number) => [value.toFixed(1), METRICS.find(m => m.key === metric)?.label]}
                />
                <ReferenceLine x={100} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} isAnimationActive={false}>
                  {chartData.map((d, idx) => (
                    <Cell
                      key={idx}
                      fill={d.value >= 100 ? "hsl(142 71% 45% / 0.85)" : "hsl(0 72% 51% / 0.85)"}
                    />
                  ))}
                  <LabelList
                    dataKey="value" position="right"
                    formatter={(v: number) => (typeof v === "number" ? v.toFixed(1) : String(v))}
                    style={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  />
                </Bar>
              </BarChart>
            </ChartContainer>
          )}
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            <Info className="w-3 h-3" />
            左侧为城市名（已列出全部 70 城），柱体末端数字即该指标值；虚线为基期 100：绿色（≥100）上涨、红色（&lt;100）下跌。数据源自国家统计局 70 城房价指数。
          </p>
        </CardContent>
      </Card>

      {/* 数据表 */}
      <Card className="glow-card border-0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ArrowUpDown className="w-4 h-4 text-primary" />
            明细数据（点击表头排序）
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground py-8 text-center">加载中...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/60 text-muted-foreground">
                    <Th onClick={() => toggleSort("rank")}>排名</Th>
                    <Th onClick={() => toggleSort("city")}>城市</Th>
                    <Th onClick={() => toggleSort("commodity_yoy")}>新房·同比</Th>
                    <Th onClick={() => toggleSort("secondhand_yoy")}>二手房·同比</Th>
                    <Th onClick={() => toggleSort("commodity_mom")}>新房·环比</Th>
                    <Th onClick={() => toggleSort("secondhand_mom")}>二手房·环比</Th>
                    <Th onClick={() => toggleSort("year")}>期次</Th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(r => (
                    <tr key={r.city} className="border-b border-border/40 hover:bg-accent/30">
                      <Td>{r.rank}</Td>
                      <Td>{r.city}</Td>
                      <Td v={r.commodity_yoy} />
                      <Td v={r.secondhand_yoy} />
                      <Td v={r.commodity_mom} />
                      <Td v={r.secondhand_mom} />
                      <Td>{r.year && r.month ? `${r.year}/${r.month}` : "-"}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Th({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <th className="px-3 py-2 text-left font-medium cursor-pointer select-none hover:text-foreground" onClick={onClick}>
      {children}
    </th>
  );
}

function Td({ children, v }: { children?: React.ReactNode; v?: number | null }) {
  if (v !== undefined) {
    const txt = v == null ? "-" : v.toFixed(1);
    const color = v == null ? "" : v >= 100 ? "text-emerald-500" : "text-red-500";
    return <td className={`px-3 py-2 tabular-nums ${color}`}>{txt}</td>;
  }
  return <td className="px-3 py-2">{children}</td>;
}
