# nlp_module/extractor.py
import re
import json


class TextExtractor:
    @staticmethod
    def extract_price(text):
        # 匹配 "成交价 500万" 或 "500万成交"
        patterns = [
            r'成交价[：:]\s*([\d.]+)\s*万',
            r'([\d.]+)\s*万\s*成交',
            r'实际价格[：:]\s*([\d.]+)\s*万'
        ]
        for p in patterns:
            match = re.search(p, text)
            if match:
                return float(match.group(1))
        return None

    @staticmethod
    def detect_fraud_keywords(text):
        keywords = ['绝版', '最后机会', '翻倍', '仅此一套', '空前绝后']
        found = [kw for kw in keywords if kw in text]
        return found