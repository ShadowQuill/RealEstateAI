import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  LineChart, TrendingUp, Loader2, MapPin, Home, Building2, Calendar,
} from "lucide-react";
import { api } from "@/types/api";
import { formatPrice } from "@/lib/format";

const selectClass =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
  "focus-visible:ring-offset-2";

const ALL_CITIES = [
  '北京', '上海', '广州', '深圳',
  '成都', '重庆', '杭州', '武汉', '天津',
  '苏州', '南京', '西安', '郑州', '长沙',
  '合肥', '青岛', '东莞', '佛山', '宁波',
  '大连', '沈阳', '济南', '昆明', '厦门',
  '福州', '无锡', '珠海', '哈尔滨', '南宁',
];

const SUPPORTED_LAYOUTS = ['2室1厅', '3室1厅', '3室2厅'];
const SUPPORTED_FLOORS = ['低楼层', '中楼层', '高楼层'];

export default function PricePredictPage() {
  const [city, setCity] = useState('北京');
  const [area, setArea] = useState('89');
  const [layout, setLayout] = useState('3室2厅');
  const [floor, setFloor] = useState('中楼层');
  const [buildingYear, setBuildingYear] = useState('2015');
  const [tradeYear, setTradeYear] = useState('2025');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<number | null>(null);

  const handlePredict = async () => {
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

      const features: Record<string, number> = {
        year: ty,
        area: a,
        building_year: by,
      };
      ALL_CITIES.forEach((c) => { features[`city_${c}`] = c === city ? 1 : 0; });
      SUPPORTED_LAYOUTS.forEach((l) => { features[`layout_${l}`] = l === layout ? 1 : 0; });
      SUPPORTED_FLOORS.forEach((f) => { features[`floor_info_${f}`] = f === floor ? 1 : 0; });

      const res = await api.predictPrice(features);
      setResult(res.predicted_price);
    } catch (e) {
      setError(e instanceof Error ? e.message : '预测失败');
    } finally {
      setLoading(false);
    }
  };

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
              {ALL_CITIES.map((c) => (
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
                {SUPPORTED_LAYOUTS.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Building2 className="w-4 h-4 text-muted-foreground" /> 楼层
              </label>
              <select className={selectClass} value={floor} onChange={(e) => setFloor(e.target.value)}>
                {SUPPORTED_FLOORS.map((f) => (
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
                {city} · {layout} · {area}㎡ · {floor} · {buildingYear}年建 · {tradeYear}年交易
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
