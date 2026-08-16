import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, Globe2, Info, HelpCircle } from "lucide-react";
import { api } from "@/types/api";
import type { MacroData, MacroMetric } from "@/types/api";

/**
 * 每个宏观指标的「白话解释」+「为什么和房价有关」。
 * 让新手一眼看懂这张表在说什么。
 */
const METRIC_INFO: Record<string, { plain: string; housing: string }> = {
  macro_gdp_yoy: {
    plain: "国民经济整体增速：今年比去年同期多/少增长了几个百分点。",
    housing: "经济稳增长 → 大家收入和购房信心更稳；明显下滑 → 楼市预期容易走弱。",
  },
  macro_cpi_yoy: {
    plain: "居民消费价格涨幅，也就是常说的「通胀」水平。",
    housing: "温和通胀利于房产保值；过高会逼央行加息，进而抬高房贷成本。",
  },
  macro_m2_yoy: {
    plain: "广义货币（M2）供应增速，反映「市面上流通的钱」增长快慢。",
    housing: "M2 高增 = 流动性充裕，其中一部分资金可能流向楼市。",
  },
  macro_pmi: {
    plain: "制造业景气「温度计」，分界点是 50（荣枯线）。",
    housing: "高于 50 经济扩张、购房意愿通常更强；低于 50 收缩、市场信心偏弱。",
  },
  macro_rate_10y: {
    plain: "10 年期国债收益率，可理解为市场「无风险利率」的锚。",
    housing: "它下行时，房贷利率往往跟着降，买房的资金成本就更低。",
  },
};

export default function MacroPage() {
  const [data, setData] = useState<MacroData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const d = await api.getMacro();
        setData(d);
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        <Skeleton className="h-10 w-72" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            宏观数据加载失败：{error}
          </CardContent>
        </Card>
      </div>
    );
  }

  const fmt = (m: MacroMetric) =>
    m.value === null || m.value === undefined ? "--" : m.value.toFixed(2);

  const isPoint = (m: MacroMetric) => m.unit === "点";

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10 text-primary">
          <Globe2 className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">当前宏观环境</h1>
          <p className="text-sm text-muted-foreground">
            {data.year ? `${data.year} 年宏观指标快照` : "宏观指标快照"} · 作为房价研判与 AI 分析的背景参考
          </p>
        </div>
      </div>

      {/* 先看这个：名词速查 */}
      <Card className="border border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <HelpCircle className="w-5 h-5 text-primary" /> 先看懂这几个词
          </CardTitle>
        </CardHeader>
        <CardContent className="grid sm:grid-cols-3 gap-3 text-sm leading-relaxed">
          <div className="rounded-lg border bg-background/60 p-3">
            <p className="font-medium mb-1">同比（%）</p>
            <p className="text-muted-foreground">和「去年同一时期」比。用来判断大趋势：正数是增长，负数是下降。</p>
          </div>
          <div className="rounded-lg border bg-background/60 p-3">
            <p className="font-medium mb-1">荣枯线 50（仅 PMI 用）</p>
            <p className="text-muted-foreground">经济的「分水岭」：大于 50 表示扩张，小于 50 表示收缩。</p>
          </div>
          <div className="rounded-lg border bg-background/60 p-3">
            <p className="font-medium mb-1">这 5 个指标是什么关系？</p>
            <p className="text-muted-foreground">GDP 看增长、CPI 看物价、M2 看「钱多不多」、PMI 看景气、10 年国债看「借钱成本」——合起来就是楼市的「天气」。</p>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {data.metrics.map((m) => {
          const info = METRIC_INFO[m.key];
          return (
            <Card key={m.key}>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1">
                  {m.label}
                  {isPoint(m) && <span className="text-[10px] text-amber-500">· 看荣枯线</span>}
                  {!isPoint(m) && <span className="text-[10px] text-sky-500">· 同比</span>}
                </CardDescription>
                <CardTitle className="text-3xl tabular-nums">
                  {fmt(m)}
                  <span className="text-base font-normal text-muted-foreground ml-1">{m.unit}</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground space-y-2">
                <p>{info?.plain ?? (isPoint(m) ? "荣枯线 50：>50 扩张，<50 收缩" : "同比（%，较去年同期）")}</p>
                {info?.housing && (
                  <p className="pt-2 border-t border-border/50 text-foreground/70">
                    <span className="font-medium text-primary/80">和房价：</span>{info.housing}
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <TrendingUp className="w-5 h-5 text-primary" /> 宏观面简评
          </CardTitle>
          <CardDescription>基于上述指标自动生成的楼市相关解读</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {data.summary.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Info className="w-3.5 h-3.5" />
        宏观数据为单年快照，仅反映当下环境，不构成投资建议。
      </p>
    </div>
  );
}
