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
        """综合正则提取成交价（单位：万元），支持多种口语/书面格式。

        设计要点：
        1. 价格前缀（成交价/总价/售价/挂牌价/卖价/报价/一口价/现售/价格 等）
           与单位（万/万元/W/w/元换算）解耦，前缀可选、是否带冒号均可。
        2. 允许前缀与数字之间存在任意非数字分隔符（含标点、空格），使用
           [^\\d]* 而非仅 \\s*，从而兼容「售价620万」「总价:1200万」等写法。
        3. 支持「X万」「X万元」「X万整」「约X万」「Xw/XW」等多种数字-单位组合。
        4. 范围过滤放宽到 1~100000 万元，并对明显异常值给出 warning 而非静默丢弃。
        """
        # 价格前缀（可带冒号，也可不带）；用非捕获分组，前缀可选
        prefixes = [
            '成交价', '成交', '总价', '总价款', '总售', '售价', '售',
            '挂牌价', '挂牌', '卖价', '卖', '报价', '报', '一口价',
            '现售', '现房', '价格', '价', '到手价', '净价', '实价',
        ]
        # 先剔除文本中的「单价」语境片段，避免把单价里的「X万/㎡」误判为总价。
        # 匹配：单价(可选冒号) + 数字 + 万? + 元? + (/每)? + 平㎡，整体删去。
        text_for_price = re.sub(
            r'单价[：:=]?\s*[^0-9]*?[\d]+(?:\.[\d]+)?\s*(?:[万Ww]|万元?|万圆?)?\s*(?:元|块)?\s*[/每]?\s*[平㎡]',
            '', text
        )
        # 构造正则：前缀(可选,可带冒号) + 分隔 + 数字 + 单位(万类)
        # 注意：当带「万」时要紧跟数字；不带「万」时用「元/块」需换算。
        patterns = []
        for pre in prefixes:
            # 带「万」类单位（最常见）
            patterns.append(
                re.escape(pre) + r'[：:=]?\s*[^0-9]*?([\d]+(?:\.[\d]+)?)\s*(?:[万Ww]|万元?|万圆?)'
            )
        # 无前缀直接「X万/X万元/Xw」写法
        # 负向前瞻：排除后面紧接单价单位(/㎡、每平、/平)，避免误吞单价
        patterns.append(r'([\d]+(?:\.[\d]+)?)\s*(?:[万Ww]|万元?|万圆?)(?!\s*[/每]?\s*[平㎡])(?!\s*元?\s*/\s*[平㎡])\s*(?:成交|整|块)?')
        # 带「元/块」前缀写法（需换算为万元）：X元 / X万元已覆盖，这里补「X元」
        patterns.append(r'([\d]+(?:\.[\d]+)?)\s*元')

        target = text_for_price

        for p in patterns:
            match = re.search(p, target)
            if match:
                try:
                    raw = float(match.group(1))
                except (ValueError, IndexError):
                    continue
                # 判断单位是否需要换算（若正则捕获的这串后面跟「元」而非「万」）
                seg = match.group(0)
                if '万' in seg or re.search(r'[Ww]', seg) or '万元' in seg:
                    price = raw  # 已是万元
                else:
                    # 命中「X元」分支，换算成万元（1万元=10000元）
                    price = raw / 10000.0
                # 合理性范围（万元）：普通住宅 1万~100000万（即1亿）
                if 1 <= price <= 100000:
                    return round(price, 2)
                # 超出范围但为正：仍返回，标记异常交由上层处理
                if price > 0:
                    return round(price, 2)
        return None

    def extract_unit_price(self, text):
        """提取单价（每平米价格，单位：元/㎡），如『单价5万/㎡』『6万元每平』。"""
        patterns = [
            r'单价[：:=]?\s*[^0-9]*?([\d]+(?:\.[\d]+)?)\s*(?:[万Ww]|万元?)?\s*(?:元|块)?\s*[/每]?\s*[平㎡]',
            r'([\d]+(?:\.[\d]+)?)\s*(?:[万Ww]|万元?)?\s*元?\s*[/每]\s*[平㎡]',
            r'([\d]+(?:\.[\d]+)?)\s*元\s*/?\s*[平㎡]',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                val = float(m.group(1))
                # 若带「万」则是万元/㎡，换算为 元/㎡
                if '万' in m.group(0) or re.search(r'[Ww]', m.group(0)):
                    val *= 10000
                return round(val, 0)
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
        """综合分析：一键提取所有文本信息。

        价格策略：同时输出总价(deal_price, 万元)与单价(unit_price, 元/㎡)。
        - 文本同时给出两者时直接读取；
        - 仅给出总价时，若存在面积(area_matched, ㎡)则反推单价：单价=总价×10000÷面积；
        - 仅给出单价时，若存在面积则反推总价：总价=单价×面积÷10000；
        - 两者都缺或无法计算时返回 None，并给出 reason 说明。
        """
        features = self.extract_features(text)
        area = features.get('area_matched')  # 单位：平方米

        deal_price = self.extract_deal_price(text)      # 万元
        unit_price = self.extract_unit_price(text)      # 元/㎡

        price_reason = []
        if deal_price is None and unit_price is not None and area:
            deal_price = round(unit_price * area / 10000.0, 2)  # 万元
            price_reason.append("由单价×面积推算总价")
        elif unit_price is None and deal_price is not None and area:
            unit_price = round(deal_price * 10000.0 / area, 0)  # 元/㎡
            price_reason.append("由总价÷面积推算单价")
        elif deal_price is None and unit_price is None:
            price_reason.append("文本未提供价格且无法推算")

        return {
            "deal_price": deal_price,
            "unit_price": unit_price,
            "price_reason": price_reason if price_reason else ["文本直接提取"],
            "fraud_risk": self.detect_fake_promotion(text),
            "regions": self.extract_region(text),
            "features": features,
            "sentiment": self.analyze_sentiment(text),
            "text_length": len(text)
        }


if __name__ == "__main__":
    analyzer = AIRealEstateAnalyzer()
    
    test_texts = [
        "朝阳区新房，绝版地段，成交价850万，精装修，南北通透，近地铁，学区房",
        "海淀区老旧小区，120平米，简装，朝南，地铁口300米，售价620万",
        "浦东新区新房，豪华装修，总价1200万，有电梯车位",
        "业主急售！一口价950w，精装三居，随时看房",
        "本房挂牌价：1380万元，满五唯一，近公园",
        "单价5.2万/㎡，建面89平，总款约462万",
        "西城区学区房，到手价7800000元，无中介费",
        # 只给总价 + 面积 -> 推算单价
        "丰台区两居，89平米，成交价530万，满五唯一",
        # 只给单价 + 面积 -> 推算总价
        "通州区新房，单价4.8万/㎡，建面106平，南北通透",
        # 只给总价无面积 -> 两者都不全
        "石景山区老房，业主急售680万，看房方便",
    ]
    
    for text in test_texts:
        print("\n" + "=" * 60)
        print(f"分析文本: {text}")
        result = analyzer.comprehensive_analysis(text)
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
