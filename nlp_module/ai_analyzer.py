"""
NLP 文本分析模块 - 增强版
支持: 成交价提取、虚假宣传检测、区域提取、房源特征提取、情感分析
"""
import re
import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 配置文件（含国内镜像 HF_ENDPOINT，加速模型加载）
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from sentence_transformers import SentenceTransformer, util
import numpy as np

# 中国主要城市区域关键词
CHINESE_REGIONS = [
    '朝阳', '海淀', '东城', '西城', '丰台', '石景山', '通州', '大兴', '顺义', '昌平',
    '浦东', '静安', '徐汇', '长宁', '黄浦', '杨浦', '虹口', '普陀', '闵行', '宝山',
    '天河', '越秀', '海珠', '荔湾', '白云', '番禺', '黄埔',
    '南山', '福田', '罗湖', '宝安', '龙岗', '龙华',
    '锦江', '武侯', '青羊', '成华', '金牛', '高新',
    '渝中', '江北', '南岸', '沙坪坝', '九龙坡',
    '西湖', '拱墅', '余杭', '萧山', '滨江',
    '河西', '和平', '南开', '河北', '河东',
    '鼓楼', '玄武', '秦淮', '建邺', '栖霞',
    '江岸', '江汉', '洪山', '武昌',
]

# 房产特征关键词
FEATURE_KEYWORDS = {
    'elevator': ['电梯', '有电梯', '无电梯', '电梯房'],
    'decoration': ['精装', '简装', '豪装', '毛坯', '普通装修', '精装修'],
    'orientation': ['朝南', '南北通透', '朝东', '朝西', '朝北', '南北', '东南', '西南'],
    'subway': ['地铁', '地铁口', '近地铁', '地铁房'],
    'school': ['学区', '学区房', '重点学校', '名校', '对口'],
    'parking': ['车位', '停车位', '车库'],
    'garden': ['花园', '露台', '阳台', '庭院'],
    'type': ['板楼', '塔楼', '别墅', '洋房', '公寓'],
}

class AIRealEstateAnalyzer:
    def __init__(self):
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        print(f"⏳ 正在加载NLP语义模型（首次需下载），缓存目录：{cache_dir} ...")
        self.model = SentenceTransformer(
            'paraphrase-multilingual-MiniLM-L12-v2',
            cache_folder=cache_dir
        )

    def extract_deal_price(self, text):
        """综合正则提取成交价，支持多种格式"""
        patterns = [
            r'成交价[：:]\s*([\d.]+)\s*万',
            r'成交价\s*([\d.]+)\s*万',
            r'([\d.]+)\s*万\s*成交',
            r'总价[：:]\s*([\d.]+)\s*万',
            r'售价[：:]\s*([\d.]+)\s*万',
            r'([\d.]+)\s*万元',
            r'挂牌价[：:]\s*([\d.]+)\s*万',
        ]
        for p in patterns:
            match = re.search(p, text)
            if match:
                price = float(match.group(1))
                if 10 < price < 50000:  # 合理的价格范围
                    return price
        return None

    def detect_fake_promotion(self, text):
        """虚假宣传识别：结合关键词库和语义阈值"""
        high_risk_words = ['绝版', '空前绝后', '翻倍暴涨', '不买后悔', '最后机会',
                          '只此一套', '超低价急售', '跳楼价', '业主急哭', '必涨无疑']
        has_high_risk = any(w in text for w in high_risk_words)

        hype_sentences = [
            "最后一天清仓甩卖",
            "买到就是赚到",
            "错过再无",
            "限时特惠抢购",
            "独家房源速抢"
        ]
        hype_emb = self.model.encode(hype_sentences, convert_to_tensor=True)
        text_emb = self.model.encode(text, convert_to_tensor=True)
        cos_scores = util.cos_sim(text_emb, hype_emb)
        avg_score = float(np.mean(cos_scores.cpu().numpy()))

        risk_level = "低"
        risk_reasons = []
        
        if has_high_risk:
            risk_level = "高"
            risk_reasons.append("包含高危宣传词汇")
        
        if avg_score > 0.75:
            risk_level = "高"
            risk_reasons.append(f"语义相似度过高 ({avg_score:.2f})")
        elif avg_score > 0.55:
            if risk_level != "高":
                risk_level = "中"
            risk_reasons.append(f"语义相似度偏高 ({avg_score:.2f})")

        return {
            "risk_level": risk_level,
            "hype_similarity_score": round(avg_score, 3),
            "contains_high_risk_words": has_high_risk,
            "risk_reasons": risk_reasons if risk_reasons else ["内容正常"]
        }

    def extract_region(self, text):
        """从文本中提取房产所在区域"""
        found_regions = []
        for region in CHINESE_REGIONS:
            if region in text:
                found_regions.append(region)
        return found_regions

    def extract_features(self, text):
        """从房产描述文本中提取关键特征"""
        features = {}
        for category, keywords in FEATURE_KEYWORDS.items():
            matched = []
            for kw in keywords:
                if kw in text:
                    matched.append(kw)
            if matched:
                features[category] = matched
        
        # 提取面积
        area_match = re.search(r'([\d.]+)\s*[平㎡]', text)
        if area_match:
            features['area_matched'] = float(area_match.group(1))
        
        # 提取房龄/建成年份
        year_match = re.search(r'(\d{4})\s*年[建代]', text)
        if year_match:
            features['building_year_matched'] = int(year_match.group(1))
        
        return features

    def analyze_sentiment(self, text):
        """分析文本情感倾向（正面/负面）"""
        positive_words = ['好', '棒', '优', '赞', '完美', '理想', '舒适', '温馨', 
                         '豪华', '高端', '新', '极佳', '一流', '优质', '超值']
        negative_words = ['差', '破', '旧', '烂', '糟糕', '低端', '缺陷', '噪音',
                         '潮湿', '漏水', '开裂', '拥挤', '不便', '失望']
        
        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)
        
        if pos_count > neg_count * 2:
            sentiment = "正面"
        elif neg_count > pos_count * 2:
            sentiment = "负面"
        elif pos_count > neg_count:
            sentiment = "偏正面"
        elif neg_count > pos_count:
            sentiment = "偏负面"
        else:
            sentiment = "中性"
        
        return {
            "sentiment": sentiment,
            "positive_words_count": pos_count,
            "negative_words_count": neg_count,
            "score": round((pos_count - neg_count) / max(pos_count + neg_count, 1), 2)
        }

    def comprehensive_analysis(self, text):
        """综合分析：一键提取所有文本信息"""
        return {
            "deal_price": self.extract_deal_price(text),
            "fraud_risk": self.detect_fake_promotion(text),
            "regions": self.extract_region(text),
            "features": self.extract_features(text),
            "sentiment": self.analyze_sentiment(text),
            "text_length": len(text)
        }


if __name__ == "__main__":
    analyzer = AIRealEstateAnalyzer()
    
    test_texts = [
        "朝阳区新房，绝版地段，成交价850万，精装修，南北通透，近地铁，学区房",
        "海淀区老旧小区，120平米，简装，朝南，地铁口300米，售价620万",
        "浦东新区新房，豪华装修，总价1200万，有电梯车位",
    ]
    
    for text in test_texts:
        print("\n" + "=" * 60)
        print(f"分析文本: {text}")
        result = analyzer.comprehensive_analysis(text)
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
