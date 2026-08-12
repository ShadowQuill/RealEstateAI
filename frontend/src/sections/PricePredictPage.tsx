import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  LineChart, TrendingUp, Loader2, MapPin, Home, Building2, Calendar, Palette,
} from "lucide-react";
import { api } from "@/types/api";
import { formatPrice } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";

const selectClass =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
  "focus-visible:ring-offset-2";

// 城市/户型/楼层列表从后端 /api/config/predict 获取，
// 与 utils/constants.py 保持单一数据源，变更需重新训练模型。
export default function PricePredictPage() {
  const [config, setConfig] = useState<{ cities: string[]; layouts: string[]; floors: string[]; decorations: string[]; orientations: string[] } | null>(null);
  const [city, setCity] = useState('');
  const [area, setArea] = useState('89');
  const [layout, setLayout] = useState('');
  const [floor, setFloor] = useState('');
  const [decoration, setDecoration] = useState('');
  const [orientation, setOrientation] = useState('');
  const [buildingYear, setBuildingYear] = useState('2015');
  const [tradeYear, setTradeYear] = useState('2025');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<number | null>(null);

  useEffect(() => {
    api.getPredictConfig().then(cfg => {
      setConfig(cfg);
      setCity(cfg.cities[0] || '');
      setLayout(cfg.layouts[0] || '');
      setFloor(cfg.floors[0] || '');
      setDecoration(cfg.decorations?.[0] || '');
      setOrientation(cfg.orientations?.[0] || '');
    });
  }, []);

  const handlePredict = async () => {
    if (!config) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const a = parseFloat(area);
      const by = parseInt(buildingYear, 10);
      const ty = parseInt(tradeYear, 10);
      if (!a || a <= 0) throw new Error('请输入有效的面积');
      if (!by || by <= 1900) throw new Error('请输入有效的建成年份');
      if (!ty || ty < 1990) throw new Error('请输入有效的交易年份');

      const features: Record<string, number | string> = {
        year: ty,
        area: a,
        building_year: by,
      };
      config.cities.forEach((c) => { features[`city_${c}`] = c === city ? 1 : 0; });
      config.layouts.forEach((l) => { features[`layout_${l}`] = l === layout ? 1 : 0; });
      config.floors.forEach((f) => { features[`floor_info_${f}`] = f === floor ? 1 : 0; });
      features['decoration'] = decoration;
      features['orientation'] = orientation;

      const res = await api.predictPrice(features);
      setResult(res.predicted_price);
    } catch (e) {
      setError(e instanceof Error ? e.message : '预测失败');
    } finally {
      setLoading(false);
    }
  };

  if (!config) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10">
          <LineChart className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">AI 价格预测</h1>
          <p className="text-sm text-muted-foreground">输入房源特征，预测二手房总价（万元）</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">房源特征</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* 城市 */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm font-medium">
              <MapPin className="w-4 h-4 text-muted-foreground" /> 城市
            </label>
            <select className={selectClass} value={city} onChange={(e) => setCity(e.target.value)}>
              {config.cities.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* 面积 + 建成年份 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Home className="w-4 h-4 text-muted-foreground" /> 面积（㎡）
              </label>
              <Input type="number" value={area} onChange={(e) => setArea(e.target.value)} placeholder="如 89" />
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Building2 className="w-4 h-4 text-muted-foreground" /> 建成年份
              </label>
              <Input type="number" value={buildingYear} onChange={(e) => setBuildingYear(e.target.value)} placeholder="如 2015" />
            </div>
          </div>

          {/* 户型 + 楼层 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Home className="w-4 h-4 text-muted-foreground" /> 户型
              </label>
              <select className={selectClass} value={layout} onChange={(e) => setLayout(e.target.value)}>
                {config.layouts.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Building2 className="w-4 h-4 text-muted-foreground" /> 楼层
              </label>
              <select className={selectClass} value={floor} onChange={(e) => setFloor(e.target.value)}>
                {config.floors.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>
          </div>

          {/* 交易年份 */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm font-medium">
              <Calendar className="w-4 h-4 text-muted-foreground" /> 交易年份
            </label>
            <Input type="number" value={tradeYear} onChange={(e) => setTradeYear(e.target.value)} placeholder="如 2025" />
          </div>

          {/* 装修 + 朝向 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Palette className="w-4 h-4 text-muted-foreground" /> 装修
              </label>
              <select className={selectClass} value={decoration} onChange={(e) => setDecoration(e.target.value)}>
                {config.decorations.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Palette className="w-4 h-4 text-muted-foreground" /> 朝向
              </label>
              <select className={selectClass} value={orientation} onChange={(e) => setOrientation(e.target.value)}>
                {config.orientations.map((o) => (
                  <option key={o} value={o}>{o}</option>
                ))}
              </select>
            </div>
          </div>

          <Button onClick={handlePredict} disabled={loading} className="w-full">
            <span className="inline-flex w-4 h-4 items-center justify-center">
              <Loader2 className={`w-4 h-4 animate-spin${loading ? '' : ' hidden'}`} />
              <TrendingUp className={`w-4 h-4${loading ? ' hidden' : ''}`} />
            </span>
            {loading ? '预测中…' : '开始预测'}
          </Button>

          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {result !== null && !loading && (
            <div className="rounded-lg border bg-primary/5 p-6 text-center">
              <p className="text-sm text-muted-foreground">AI 预测总价</p>
              <p className="mt-1 text-4xl font-bold text-primary">{formatPrice(result)}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                {city} · {layout} · {area}㎡ · {floor} · {decoration} · {orientation} · {buildingYear}年建 · {tradeYear}年交易
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
