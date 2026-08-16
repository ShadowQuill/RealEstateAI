# data_pipeline/macro_features.py
"""宏观数据加载与简评底座。

把 data/macro_data 下抓取的中国宏观经济指标（GDP 同比、CPI 同比、
M2 同比、制造业 PMI、10 年国债收益率）解析为「当前宏观环境」快照，
供前端展示面板与 AI 分析 / 趋势研判作为真实上下文。

数据形态说明（重要）：
  抓取的宏观数据均为**单年（2026）快照**（月/季/日频），不含历史年度序列。
  因此本模块定位为"当下宏观环境"展示与上下文，而非历史价格模型特征——
  把单年常量硬塞进跨年价格特征无增益（scaler 后方差≈0）。
  - get_current_macro()：当前宏观快照（展示 / AI 上下文用）
  - get_macro_for_year()：按年取数（保留为 2027+ 预测的特征扩展点）
"""
import os
import re
import json
from collections import defaultdict

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MACRO_DIR = os.path.join(BASE_DIR, 'data', 'macro_data')

# 宏观指标元信息（key 即数据列名，label / unit 用于展示）
MACRO_METRICS = [
    {'key': 'macro_gdp_yoy',  'label': 'GDP 同比',       'unit': '%',  'fmt': '%.2f'},
    {'key': 'macro_cpi_yoy',  'label': 'CPI 同比',       'unit': '%',  'fmt': '%.2f'},
    {'key': 'macro_m2_yoy',   'label': 'M2 同比',        'unit': '%',  'fmt': '%.2f'},
    {'key': 'macro_pmi',      'label': '制造业 PMI',     'unit': '点', 'fmt': '%.2f'},
    {'key': 'macro_rate_10y', 'label': '10Y 国债收益率', 'unit': '%',  'fmt': '%.2f'},
]
MACRO_KEYS = [m['key'] for m in MACRO_METRICS]

# 年份解析：支持 14 位时间戳(20260630000000) 与 YYYY-MM-DD
_YEAR_RE = re.compile(r'(\d{4})')


def _year_from(cell):
    m = _YEAR_RE.search(str(cell))
    if m:
        y = int(m.group(1))
        if 1990 <= y <= 2035:
            return y
    return None


def _parse_md_table(content):
    """解析 markdown 表格，返回行（单元格列表）。跳过表头与分隔行。"""
    rows = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith('|'):
            continue
        if re.match(r'^\|[\s:|-]+\|$', line):  # 分隔行
            continue
        rows.append([c.strip() for c in line.strip('|').split('|')])
    return rows[1:] if len(rows) > 1 else []  # 去掉表头


def _load_json_tables(fname):
    """读取一个宏观 JSON 文件，返回其中所有 apiRecall 的 markdown 表格行列表。"""
    path = os.path.join(MACRO_DIR, fname)
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        return []
    apis = (d.get('data') or {}).get('apiData', {}).get('apiRecall', []) or []
    out = []
    for a in apis:
        out.extend(_parse_md_table(a.get('content', '') or ''))
    return out


def _to_float(v):
    try:
        return float(str(v).replace(',', '').replace('%', '').strip())
    except Exception:
        return None


def _is_date_cell(s):
    s = str(s).strip()
    if re.fullmatch(r'\d{14}', s):
        return True
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return True
    return False


def _first_match(rows, must_contain, prefer_contain=None):
    """在表格行中按指标名匹配，返回 (year, value)。

    各宏观文件列布局不完全一致（指标名在首列或次列、年份列位置不同），
    故不依赖固定列下标，而是：
      - 指标名：包含全部 must_contain 关键词的最左单元格；
      - 年份：首个"日期型"单元格（14 位时间戳或 YYYY-MM-DD）；
      - 数值：首个"非日期型、可转 float"的单元格。
    prefer_contain：若某指标名额外含这些词则优先（如 '年' 优先于 '月'）。
    """
    candidates = []
    for r in rows:
        name_cell = None
        for c in r:
            if all(k in str(c) for k in must_contain):
                name_cell = str(c)
                break
        if name_cell is None:
            continue
        yr = None
        for c in r:
            if _is_date_cell(c):
                yr = _year_from(c)
                if yr:
                    break
        val = None
        for c in r:
            if _is_date_cell(c):
                continue
            v = _to_float(c)
            if v is not None:
                val = v
                break
        if yr is None or val is None:
            continue
        score = 1 if (prefer_contain and any(p in name_cell for p in prefer_contain)) else 0
        candidates.append((score, yr, val))
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    best_score = candidates[0][0]
    top = [c for c in candidates if c[0] == best_score]
    yr = top[0][1]
    val = sum(c[2] for c in top) / len(top)
    return yr, round(val, 4)


def _parse_pmi():
    rows = _load_json_tables('pmi.json')
    vals = []
    for r in rows:
        name_cell = r[0] if r else ''
        if '制造业PMI' in name_cell and '季调' in name_cell and '月' in name_cell:
            yr = None
            for c in r:
                if _is_date_cell(c):
                    yr = _year_from(c)
                    if yr:
                        break
            val = None
            for c in r:
                if _is_date_cell(c):
                    continue
                v = _to_float(c)
                if v is not None:
                    val = v
                    break
            if yr and val is not None:
                vals.append((yr, val))
    if not vals:
        return None
    yr = vals[0][0]
    return yr, round(sum(v for _, v in vals) / len(vals), 4)


def _parse_rate():
    """10 年国债收益率：取所有日度值均值。"""
    rows = _load_json_tables('rate.json')
    vals = []
    for r in rows:
        name = r[1] if len(r) >= 2 and r[1] else (r[0] if r else '')
        if '10年' in name:
            yr = _year_from(r[2] if len(r) > 2 else r[0])  # 数据日期
            val = _to_float(r[5] if len(r) > 5 else r[-1])
            if yr and val is not None:
                vals.append(val)
    if not vals:
        return None
    return 2026, round(sum(vals) / len(vals), 4)


def build_macro_table():
    """解析全部宏观文件，返回 DataFrame(year, MACRO_KEYS...) 单年（2026）表。"""
    gdp = _first_match(_load_json_tables('gdp_yoy.json'), ['GDP', '同比'])
    cpi = _first_match(_load_json_tables('cpi_yoy.json'), ['CPI', '同比'])
    # M2 同比：优先"同比:年"（年度），否则取最近月度的"当期同比"
    m2 = _first_match(_load_json_tables('m2.json'), ['M2', '同比'], prefer_contain=['年'])
    if m2 is None:
        m2 = _first_match(_load_json_tables('m2b.json'), ['M2', '同比'], prefer_contain=['年'])
    pmi = _parse_pmi()
    rate = _parse_rate()

    year = 2026
    for x in (gdp, cpi, m2, pmi, rate):
        if x:
            year = x[0]
            break

    row = {col: 0.0 for col in MACRO_KEYS}
    if gdp:
        row['macro_gdp_yoy'] = gdp[1]
    if cpi:
        row['macro_cpi_yoy'] = cpi[1]
    if m2:
        row['macro_m2_yoy'] = m2[1]
    if pmi:
        row['macro_pmi'] = pmi[1]
    if rate:
        row['macro_rate_10y'] = rate[1]
    row['year'] = year

    return pd.DataFrame([row])[['year'] + MACRO_KEYS]


# 模块级缓存，避免每次推理重复解析 JSON
_TABLE_CACHE = None


def get_macro_table():
    global _TABLE_CACHE
    if _TABLE_CACHE is None:
        try:
            _TABLE_CACHE = build_macro_table()
        except Exception:
            _TABLE_CACHE = pd.DataFrame(columns=['year'] + MACRO_KEYS)
    return _TABLE_CACHE


def get_macro_for_year(year):
    """返回指定年份的宏观特征 dict（列名同 MACRO_KEYS）。

    数据只有单年快照，故对任意年份均返回该快照值（最近值填充）。
    保留此接口作为 2027+ 价格预测的特征扩展点（届时若抓到多年序列即自动生效）。
    若该年确无数据则返回全 0。
    """
    tbl = get_macro_table()
    if tbl is None or tbl.empty:
        return {c: 0.0 for c in MACRO_KEYS}
    rec = tbl.iloc[0]
    return {c: float(rec.get(c, 0.0) or 0.0) for c in MACRO_KEYS}


def _val_by_label(metrics, label):
    for m in metrics:
        if m['label'] == label:
            return m['value']
    return None


def generate_macro_summary(metrics):
    """根据当前宏观指标生成中文自动简评（短句列表）。"""
    if not metrics:
        return ['（暂无宏观数据）']
    gdp = _val_by_label(metrics, 'GDP 同比')
    cpi = _val_by_label(metrics, 'CPI 同比')
    m2 = _val_by_label(metrics, 'M2 同比')
    pmi = _val_by_label(metrics, '制造业 PMI')
    rate = _val_by_label(metrics, '10Y 国债收益率')
    s = []
    if gdp is not None:
        if gdp < 4:
            s.append(f'GDP 同比仅 {gdp:.1f}%，经济基本面承压')
        elif gdp < 5.5:
            s.append(f'GDP 同比 {gdp:.1f}%，增速温和偏弱')
        else:
            s.append(f'GDP 同比 {gdp:.1f}%，经济保持较快增长')
    if cpi is not None:
        if cpi < 1:
            s.append(f'CPI 同比 {cpi:.1f}%，低位运行、存在通缩隐忧')
        elif cpi > 3:
            s.append(f'CPI 同比 {cpi:.1f}%，通胀有所升温')
        else:
            s.append(f'CPI 同比 {cpi:.1f}%，物价总体平稳')
    if m2 is not None:
        if m2 > 10:
            s.append(f'M2 同比 {m2:.1f}%，货币供应偏宽松')
        elif m2 < 8:
            s.append(f'M2 同比 {m2:.1f}%，信用扩张偏紧')
        else:
            s.append(f'M2 同比 {m2:.1f}%，流动性中性')
    if pmi is not None:
        if pmi < 50:
            s.append(f'制造业 PMI {pmi:.1f}（<50），景气收缩、利空房价预期')
        else:
            s.append(f'制造业 PMI {pmi:.1f}（≥50），景气扩张')
    if rate is not None:
        if rate < 2:
            s.append(f'10Y 国债收益率 {rate:.2f}%，利率处低位、购房成本下降')
        else:
            s.append(f'10Y 国债收益率 {rate:.2f}%，处于常态区间')
    return s


def get_current_macro():
    """返回当前宏观环境快照（供前端展示与 AI 上下文）。

    结构：{'year': int|None, 'metrics': [{key,label,value,unit,fmt}], 'summary': [str]}
    """
    tbl = get_macro_table()
    if tbl is None or tbl.empty:
        return {'year': None, 'metrics': [], 'summary': ['（暂无宏观数据）']}
    rec = tbl.iloc[0]
    year = int(rec.get('year', 2026))
    metrics = []
    for m in MACRO_METRICS:
        val = rec.get(m['key'])
        metrics.append({
            'key': m['key'],
            'label': m['label'],
            'value': None if pd.isna(val) else float(val),
            'unit': m['unit'],
            'fmt': m['fmt'],
        })
    return {'year': year, 'metrics': metrics, 'summary': generate_macro_summary(metrics)}


if __name__ == '__main__':
    import json as _json
    pd.set_option('display.width', 120)
    print("当前宏观环境：")
    print(_json.dumps(get_current_macro(), ensure_ascii=False, indent=2))
