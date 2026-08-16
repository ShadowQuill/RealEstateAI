"""
RAG 记忆/检索层（防幻觉）

设计目标：让 /api/analyze 类问答「基于项目真实数据」回答，而非让 LLM 凭空生成。
- 检索器：用 sklearn TF-IDF（字符 n-gram）在真实语料上建索引，零额外重依赖
  （scikit-learn 已在精简部署依赖中），本地与 Docker slim 镜像均可运行。
- 语料来源：项目简介、当前宏观环境快照、国家统计局城市房价指数、房源统计、
  项目文档（README）。全部为项目内真实数据，绝不编造。
- 防幻觉策略：
  1. 先检索 top-k 真实片段作为上下文；
  2. 若配置了 LLM（OPENAI_API_KEY），把上下文 + 严格引用要求喂给模型；
  3. 若未配置 LLM，直接返回检索原文摘录（grounded=True），从根本上杜绝编造。
"""
import os
from typing import Dict, List, Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SK = True
except Exception:
    HAS_SK = False

# 进程内缓存（演示为单 worker，构建一次即可）
_CORPUS: Optional[List[Dict]] = None
_VECTORIZER = None
_MATRIX = None

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _chunk_text(text: str, max_chars: int = 360) -> List[str]:
    """把长文档按空行/标题切成小块，便于检索与引用。"""
    chunks: List[str] = []
    buf = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if buf:
                chunks.append(buf)
                buf = ""
            continue
        if len(buf) + len(line) + 1 <= max_chars:
            buf = (buf + "\n" + line).strip()
        else:
            if buf:
                chunks.append(buf)
            buf = line
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) > 4]


def build_corpus() -> List[Dict]:
    """构建检索语料（每条含 text 与 source）。"""
    docs: List[Dict] = []

    # 1) 项目简介（固定知识）
    docs.append({
        "text": "RealEstateAI 是一个房地产 AI 分析系统，覆盖二手房价格预测、城市房价趋势研判与 AI 房源文本分析，"
                "整合 54 城真实房源与国家统计局 70 城房价指数。价格预测采用 XGBoost + 随机森林加权融合模型，"
                "趋势预测基于真实成交与官方指数。系统定位为估值/定价辅助工具，而非投资预测。",
        "source": "项目简介",
    })

    # 2) 当前宏观环境快照
    try:
        from data_pipeline.macro_features import get_current_macro
        m = get_current_macro()
        for met in m.get("metrics", []):
            val = met.get("value")
            unit = met.get("unit", "")
            docs.append({
                "text": f"当前宏观环境（{m.get('year')}）：{met.get('label')}为{val}{unit}。",
                "source": "宏观环境",
            })
        for s in m.get("summary", []):
            docs.append({"text": s, "source": "宏观环境"})
    except Exception as e:
        print(f"⚠️ RAG 语料-宏观加载失败: {e}")

    # 3) 国家统计局城市房价指数（最新一期，同比/环比）
    try:
        from utils.database import SessionLocal, CityIndex
        db = SessionLocal()
        rows = db.query(
            CityIndex.city, CityIndex.base_type, CityIndex.year,
            CityIndex.month, CityIndex.commodity_idx, CityIndex.secondhand_idx,
        ).all()
        db.close()
        latest: Dict = {}
        for r in rows:
            key = (r.city, r.base_type)
            cur = (r.year, r.month)
            if key not in latest or cur > latest[key][0]:
                latest[key] = (cur, r)
        for (city, bt), (_, r) in latest.items():
            docs.append({
                "text": f"{city} 国家统计局房价指数（{bt}）：新房商品住宅指数 {r.commodity_idx}，"
                        f"二手房指数 {r.secondhand_idx}（{r.year}年{r.month}月）。",
                "source": f"房价指数·{city}",
            })
    except Exception as e:
        print(f"⚠️ RAG 语料-房价指数加载失败: {e}")

    # 4) 房源统计（按均价 Top 城市）
    try:
        from utils.database import SessionLocal, House
        from sqlalchemy import func
        db = SessionLocal()
        top = (
            db.query(House.city, func.count(House.id), func.avg(House.price))
            .group_by(House.city)
            .order_by(func.avg(House.price).desc())
            .limit(20)
            .all()
        )
        db.close()
        for city, cnt, avg in top:
            docs.append({
                "text": f"{city}：共 {cnt} 套房源样本，平均总价约 {round(avg or 0, 1)} 万元。",
                "source": "房源统计",
            })
    except Exception as e:
        print(f"⚠️ RAG 语料-房源统计加载失败: {e}")

    # 5) 项目文档（README）
    try:
        readme_path = os.path.join(_PROJECT_ROOT, "README.md")
        with open(readme_path, encoding="utf-8") as f:
            readme = f.read()
        for chunk in _chunk_text(readme):
            docs.append({"text": chunk, "source": "项目文档(README)"})
    except Exception as e:
        print(f"⚠️ RAG 语料-README 加载失败: {e}")

    return docs


def get_retriever():
    """返回 (corpus, vectorizer, matrix)，首次调用时构建并缓存。"""
    global _CORPUS, _VECTORIZER, _MATRIX
    if _CORPUS is not None:
        return _CORPUS, _VECTORIZER, _MATRIX
    if not HAS_SK:
        return None, None, None
    docs = build_corpus()
    texts = [d["text"] for d in docs]
    # 中文无需分词：字符 n-gram TF-IDF 即可获得稳健语义召回
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, max_df=0.9)
    mat = vec.fit_transform(texts)
    _CORPUS, _VECTORIZER, _MATRIX = docs, vec, mat
    return _CORPUS, _VECTORIZER, _MATRIX


def retrieve(query: str, k: int = 5) -> List[Dict]:
    """返回与 query 最相关的 top-k 真实片段（含 source 与 score）。"""
    docs, vec, mat = get_retriever()
    if docs is None or vec is None or mat is None:
        return []
    q = vec.transform([query])
    import numpy as np
    sims = cosine_similarity(q, mat)[0]
    idx = np.argsort(-sims)[:k]
    return [
        {"text": docs[i]["text"], "source": docs[i]["source"], "score": round(float(sims[i]), 4)}
        for i in idx if sims[i] > 0.01
    ]


def answer(query: str, llm_fn=None, k: int = 5) -> Dict:
    """基于真实数据回答。

    - llm_fn 为 None：返回检索原文摘录（grounded=True，零编造）。
    - llm_fn 提供时：拼接上下文与严格引用要求，交由 LLM 生成。
    """
    ctx = retrieve(query, k)
    if not ctx:
        return {
            "answer": "暂无相关真实数据可回答该问题。",
            "sources": [],
            "grounded": False,
            "context": [],
        }
    if llm_fn is None:
        return {
            "answer": "（未配置 LLM，以下为检索到的真实数据片段，未做生成）",
            "sources": ctx,
            "grounded": True,
            "context": ctx,
        }
    prompt = _build_prompt(query, ctx)
    generated = llm_fn(prompt)
    return {
        "answer": generated,
        "sources": ctx,
        "grounded": True,
        "context": ctx,
    }


def _build_prompt(query: str, ctx: List[Dict]) -> str:
    blocks = []
    for i, c in enumerate(ctx, 1):
        blocks.append(f"[{i}]（来源：{c['source']}）\n{c['text']}")
    context = "\n\n".join(blocks)
    return (
        "下面是来自 RealEstateAI 系统的【真实数据片段】，请仅依据这些内容回答用户问题。\n"
        "严格要求：\n"
        "1. 不得编造数据片段之外的任何数字、结论或来源；\n"
        "2. 若数据不足以回答，明确说明『根据现有数据无法确定』；\n"
        "3. 回答末尾用『来源：[1][2]…』标注引用了哪些片段。\n\n"
        f"===== 真实数据 =====\n{context}\n===== 真实数据结束 =====\n\n"
        f"用户问题：{query}\n\n回答："
    )
