# nlp_module/ai_analyzer.py
import re
import os
from sentence_transformers import SentenceTransformer, util
import numpy as np

class AIRealEstateAnalyzer:
    def __init__(self):
        # 使用 cache_folder 指定模型下载到项目根目录的 cache/ 文件夹
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        # 如果目录不存在，会自动创建（SentenceTransformer 会创建）
        print(f"⏳ 正在加载NLP语义模型（首次需下载），缓存目录：{cache_dir} ...")
        self.model = SentenceTransformer(
            'paraphrase-multilingual-MiniLM-L12-v2',
            cache_folder=cache_dir
        )

    def extract_deal_price(self, text):
        """综合正则+语义提取成交价"""
        # 匹配 "成交价850万"、"成交价: 850万"、"850万成交" 等多种写法
        patterns = [
            r'成交价[：:]\s*([\d.]+)\s*万',  # 带冒号
            r'成交价\s*([\d.]+)\s*万',  # 🔥 新增：不带冒号（直接相连）
            r'([\d.]+)\s*万\s*成交'  # 850万成交
        ]
        for p in patterns:
            match = re.search(p, text)
            if match:
                return float(match.group(1))
        return None

    def detect_fake_promotion(self, text):
        """虚假宣传识别：结合关键词库和语义阈值"""
        # 绝对高危词汇（直接标红）
        high_risk_words = ['绝版', '空前绝后', '翻倍暴涨']
        has_high_risk = any(w in text for w in high_risk_words)

        # 语义对比：计算文本与"真实降价促销"的相似度，如果极度夸张则加分
        hype_sentences = [
            "最后一天清仓甩卖",
            "买到就是赚到",
            "错过再无"
        ]
        hype_emb = self.model.encode(hype_sentences, convert_to_tensor=True)
        text_emb = self.model.encode(text, convert_to_tensor=True)
        cos_scores = util.cos_sim(text_emb, hype_emb)
        avg_score = float(np.mean(cos_scores.cpu().numpy()))

        # 综合判断
        risk_level = "低"
        if has_high_risk or avg_score > 0.75:
            risk_level = "高"
        elif avg_score > 0.55:
            risk_level = "中"

        return {
            "risk_level": risk_level,
            "hype_similarity_score": round(avg_score, 3),
            "contains_high_risk_words": has_high_risk
        }


if __name__ == "__main__":
    # 测试
    analyzer = AIRealEstateAnalyzer()
    test_text = "朝阳区新房，绝版地段，成交价850万"
    print("提取价格:", analyzer.extract_deal_price(test_text))
    print("风险检测:", analyzer.detect_fake_promotion(test_text))