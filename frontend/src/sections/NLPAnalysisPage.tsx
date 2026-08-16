import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Sparkles, Shield, AlertTriangle, MapPin, Smile,
  Frown, Tag, FileText, ArrowLeft, Hash
} from "lucide-react";
import { api } from "@/types/api";
import type { NLPAnalysis } from "@/types/api";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function NLPAnalysisPage() {
  const [searchParams] = useSearchParams();
  const listingId = searchParams.get("listing_id");

  const [text, setText] = useState("");
  const [analysis, setAnalysis] = useState<NLPAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [listingInfo, setListingInfo] = useState<{ title: string; city: string; price: number | null } | null>(null);

  // RAG 问答（基于真实数据）
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaAnswer, setQaAnswer] = useState("");
  const [qaSources, setQaSources] = useState<{ text: string; source: string; score: number }[]>([]);
  const [qaGrounded, setQaGrounded] = useState<boolean | null>(null);
  const [qaLlm, setQaLlm] = useState(false);
  const [qaLoading, setQaLoading] = useState(false);

  useEffect(() => {
    if (listingId) {
      api.analyzeListing(Number(listingId)).then(res => {
        if (res.analysis) {
          setAnalysis(res.analysis);
          setListingInfo({ title: res.title, city: res.city, price: res.price });
        }
      }).catch(console.error);
    }
  }, [listingId]);

  const handleAnalyze = async () => {
    if (!text.trim()) return;
    setLoading(true);
    try {
      const result = await api.analyzeText(text);
      setAnalysis(result);
      setListingInfo(null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleQa = async () => {
    if (!qaQuestion.trim()) return;
    setQaLoading(true);
    try {
      const res = await api.qaAnalyze(qaQuestion);
      setQaAnswer(res.answer);
      setQaSources(res.sources);
      setQaGrounded(res.grounded);
      setQaLlm(res.llm_enabled);
    } catch (e) {
      console.error(e);
      setQaAnswer("问答请求失败，请确认后端已启动且 RAG 模块可用。");
      setQaSources([]);
      setQaGrounded(null);
    } finally {
      setQaLoading(false);
    }
  };

  const riskConfig = {
    '低': { icon: Shield, color: 'text-emerald-500', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
    '中': { icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
    '高': { icon: AlertTriangle, color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  };

  const sentimentConfig = {
    '正面': { icon: Smile, color: 'text-emerald-500' },
    '负面': { icon: Frown, color: 'text-red-500' },
    '偏正面': { icon: Smile, color: 'text-emerald-400' },
    '偏负面': { icon: Frown, color: 'text-orange-400' },
    '中性': { icon: Smile, color: 'text-muted-foreground' },
  };

  const risk = analysis?.fraud_risk?.risk_level || '低';
  const riskConfigEntry = riskConfig[risk as keyof typeof riskConfig];
  const RiskIcon = riskConfigEntry?.icon || Shield;
  const riskColor = riskConfigEntry?.color || '';
  const riskBg = riskConfigEntry?.bg || '';
  const riskBorder = riskConfigEntry?.border || '';

  const sentiment = analysis?.sentiment?.sentiment || '中性';
  const sentimentEntry = sentimentConfig[sentiment as keyof typeof sentimentConfig];
  const SentimentIcon = sentimentEntry?.icon || Smile;
  const sentimentColor = sentimentEntry?.color || '';

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="w-5 h-5 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight">NLP 文本分析</h1>
        </div>
        <p className="text-muted-foreground">智能识别房产文本中的价格、风险、区域和情感信息</p>
      </div>

      {listingId && listingInfo && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <ArrowLeft className="w-4 h-4" />
          <Link to={`/predict/${listingId}`} className="hover:text-foreground transition-colors">
            {listingInfo.title}
          </Link>
          <span>|</span>
          <span>{listingInfo.city} · {formatPrice(listingInfo.price)}</span>
        </div>
      )}

      {/* Input */}
      <Card className="glow-card border-0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="w-4 h-4 text-primary" />
            输入房产描述文本
          </CardTitle>
          <CardDescription>粘贴链家、贝壳等平台的房源描述，或输入任意房产相关文本</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            placeholder="例如：朝阳区核心地段，南北通透精装三居室，成交价850万，紧邻地铁..."
            rows={5}
            value={text}
            onChange={e => setText(e.target.value)}
            className="resize-none"
            disabled={loading}
          />
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">{text.length} 字</p>
            <Button onClick={handleAnalyze} disabled={loading || !text.trim()} className="gap-2">
              <span className="inline-flex w-4 h-4 items-center justify-center">
                <span className={cn("animate-spin", loading ? "" : "hidden")}>⏳</span>
                <Sparkles className={cn("w-4 h-4", loading ? "hidden" : "")} />
              </span>
              {loading ? "分析中..." : "开始分析"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* RAG 问答（基于真实数据，防幻觉） */}
      <Card className="glow-card border-0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="w-4 h-4 text-primary" />
            AI 智能问答（基于真实数据）
          </CardTitle>
          <CardDescription>
            检索项目真实数据（宏观环境 / 房价指数 / 房源统计 / 文档）后作答；未配置 LLM 时返回原文摘录，绝不编造。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-2">
            <Textarea
              placeholder="例如：当前宏观环境对房价有什么影响？北京和上海的房价指数谁涨得多？"
              rows={2}
              value={qaQuestion}
              onChange={e => setQaQuestion(e.target.value)}
              className="resize-none"
              disabled={qaLoading}
            />
            <Button onClick={handleQa} disabled={qaLoading || !qaQuestion.trim()} className="gap-2 sm:self-end whitespace-nowrap">
              <span className={cn("animate-spin", qaLoading ? "" : "hidden")}>⏳</span>
              {qaLoading ? "检索中..." : "提问"}
            </Button>
          </div>

          {qaGrounded !== null && (
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant={qaGrounded ? "default" : "secondary"} className="gap-1">
                {qaGrounded ? "已基于真实数据" : "无相关数据"}
              </Badge>
              <Badge variant="outline" className="gap-1">
                {qaLlm ? "LLM 生成" : "原文摘录（未启用 LLM）"}
              </Badge>
            </div>
          )}

          {qaAnswer && (
            <div className="rounded-lg bg-accent/50 p-3 text-sm leading-relaxed whitespace-pre-wrap">
              {qaAnswer}
            </div>
          )}

          {qaSources.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">引用来源（{qaSources.length} 条真实数据片段）：</p>
              <div className="space-y-1.5">
                {qaSources.map((s, i) => (
                  <div key={i} className="rounded border border-border/60 bg-background/50 p-2 text-xs">
                    <span className="inline-block mb-1 rounded bg-primary/10 px-1.5 py-0.5 text-primary">[{i + 1}] {s.source}</span>
                    <p className="text-muted-foreground">{s.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {analysis && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 成交价 / 单价 */}
          <Card className="glow-card border-0">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Tag className="w-4 h-4 text-primary" />
                提取成交价与单价
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-xs text-muted-foreground">成交总价</p>
                <p className="text-3xl font-bold text-primary">{formatPrice(analysis.deal_price)}</p>
              </div>
              <div className="border-t border-border/60 pt-3">
                <p className="text-xs text-muted-foreground">单价（元/㎡）</p>
                <p className="text-xl font-semibold">
                  {analysis.unit_price != null
                    ? `${analysis.unit_price.toLocaleString()} 元/㎡`
                    : "未提取到单价"}
                </p>
              </div>
              {analysis.price_reason && analysis.price_reason.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {analysis.price_reason.join("；")}
                </p>
              )}
            </CardContent>
          </Card>

          {/* 风险 */}
          <Card className={cn("glow-card border-0", riskBorder, "border-l-4")}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <RiskIcon className={cn("w-4 h-4", riskColor)} />
                虚假宣传风险
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <Badge className={cn("text-sm px-3 py-1", riskBg, riskColor)}>
                  {risk}风险
                </Badge>
                <span className="text-sm text-muted-foreground">
                  相似度: {analysis.fraud_risk?.hype_similarity_score?.toFixed(3)}
                </span>
              </div>
              <div className="mt-2 space-y-1">
                {analysis.fraud_risk?.risk_reasons?.map((r, i) => (
                  <p key={i} className="text-xs text-muted-foreground">{r}</p>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* 区域 */}
          <Card className="glow-card border-0">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <MapPin className="w-4 h-4 text-primary" />
                识别区域
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1.5">
                {analysis.regions?.length > 0 ? analysis.regions.map(r => (
                  <Badge key={r} variant="secondary" className="gap-1">
                    <MapPin className="w-3 h-3" />{r}
                  </Badge>
                )) : (
                  <p className="text-sm text-muted-foreground">未识别到区域信息</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* 情感 */}
          <Card className="glow-card border-0">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <SentimentIcon className={cn("w-4 h-4", sentimentColor)} />
                情感分析
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className={cn("text-xl font-bold", sentimentColor)}>{sentiment}</p>
              <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                <span>正面词: {analysis.sentiment?.positive_words_count || 0}</span>
                <span>负面词: {analysis.sentiment?.negative_words_count || 0}</span>
                <span>得分: {analysis.sentiment?.score}</span>
              </div>
            </CardContent>
          </Card>

          {/* 特征 */}
          <Card className="glow-card border-0 md:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <Hash className="w-4 h-4 text-primary" />
                房源特征提取
              </CardTitle>
            </CardHeader>
            <CardContent>
              {analysis.features && Object.keys(analysis.features).length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                  {Object.entries(analysis.features).map(([cat, vals]) => {
                    if (typeof vals === 'number') {
                      return (
                        <div key={cat} className="bg-accent/50 rounded-lg p-3">
                          <p className="text-xs text-muted-foreground">{cat}</p>
                          <p className="font-semibold text-sm">{vals}</p>
                        </div>
                      );
                    }
                    return (
                      <div key={cat} className="bg-accent/50 rounded-lg p-3">
                        <p className="text-xs text-muted-foreground mb-1">{cat}</p>
                        <div className="flex flex-wrap gap-1">
                          {(vals as string[]).map(v => (
                            <Badge key={v} variant="outline" className="text-xs">{v}</Badge>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">未提取到特征信息</p>
              )}
            </CardContent>
          </Card>

          {/* Text Stats */}
          <Card className="glow-card border-0 md:col-span-2">
            <CardContent className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <FileText className="w-4 h-4" />
                文本长度: {analysis.text_length} 字
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
