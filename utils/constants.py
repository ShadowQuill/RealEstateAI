# utils/constants.py
"""全项目共享的领域常量。

单一数据源（single source of truth）：城市列表、户型/楼层取值及其
清洗与标准化逻辑集中在此，供爬虫、特征工程、API、看板共同引用，
避免多处硬编码导致的不一致。
"""
import re

# ---------------------------------------------------------------
# 城市：名称 -> 链家/贝壳 URL 前缀
# ---------------------------------------------------------------
CITY_URL_MAP = {
    # 一线
    '北京': 'bj',
    '上海': 'sh',
    '广州': 'gz',
    '深圳': 'sz',
    # 新一线 / 二线
    '成都': 'cd',
    '重庆': 'cq',
    '杭州': 'hz',
    '武汉': 'wh',
    '天津': 'tj',
    '苏州': 'su',
    '南京': 'nj',
    '西安': 'xa',
    '郑州': 'zz',
    '长沙': 'cs',
    '合肥': 'hf',
    '青岛': 'qd',
    '东莞': 'dg',
    '佛山': 'fs',
    '宁波': 'nb',
    '大连': 'dl',
    '沈阳': 'sy',
    '济南': 'jn',
    '昆明': 'km',
    '厦门': 'xm',
    '福州': 'fz',
    '无锡': 'wx',
    '珠海': 'zh',
    '哈尔滨': 'hrb',
    '南宁': 'nn',
}

# 特征列顺序依赖此列表，调整顺序需重新训练模型
ALL_CITIES = list(CITY_URL_MAP.keys())

# ---------------------------------------------------------------
# 户型 / 楼层
# ---------------------------------------------------------------
DEFAULT_LAYOUT = '3室2厅'
DEFAULT_FLOOR = '中楼层'

# 模型与 API 支持的户型类别
SUPPORTED_LAYOUTS = ['2室1厅', '3室1厅', '3室2厅']
SUPPORTED_FLOORS = ['低楼层', '中楼层', '高楼层']

# 原始户型 -> 受支持户型 的归一映射
LAYOUT_MAP = {
    '1室0厅': '2室1厅', '1室1厅': '2室1厅', '1室2厅': '2室1厅',
    '2室0厅': '2室1厅', '2室1厅': '2室1厅', '2室2厅': '2室1厅',
    '3室1厅': '3室1厅', '3室2厅': '3室2厅', '3室3厅': '3室2厅',
    '4室1厅': '3室2厅', '4室2厅': '3室2厅', '4室3厅': '3室2厅',
    '5室2厅': '3室2厅', '5室3厅': '3室2厅', '6室2厅': '3室2厅',
    '0室0厅': '3室2厅',
}

_LAYOUT_RE = re.compile(r'(\d+[室房]\d*厅?)')


def _is_blank(raw):
    """判断原始值是否为空（兼容 None / NaN / 空串）。"""
    if raw is None:
        return True
    # NaN != NaN，无需依赖 pandas 即可识别
    if isinstance(raw, float) and raw != raw:
        return True
    return not str(raw).strip()


def clean_layout(raw):
    """从混合文本中提取纯户型，如 '3室2厅 中楼层' -> '3室2厅'。"""
    if _is_blank(raw):
        return DEFAULT_LAYOUT
    m = _LAYOUT_RE.search(str(raw))
    return m.group(1) if m else DEFAULT_LAYOUT


def normalize_layout(raw):
    """清洗并归一到 SUPPORTED_LAYOUTS 之一。"""
    return LAYOUT_MAP.get(clean_layout(raw), DEFAULT_LAYOUT)


def clean_floor(raw):
    """将楼层描述归一到 SUPPORTED_FLOORS 之一。"""
    if _is_blank(raw):
        return DEFAULT_FLOOR
    s = str(raw)
    if '低' in s:
        return '低楼层'
    if '高' in s:
        return '高楼层'
    return DEFAULT_FLOOR


def build_feature_cols():
    """构造模型特征列顺序（特征工程与 API 必须保持一致）。"""
    cols = ['year', 'area', 'house_age']
    cols += [f'city_{c}' for c in ALL_CITIES]
    cols += [f'layout_{l}' for l in SUPPORTED_LAYOUTS]
    cols += [f'floor_info_{f}' for f in SUPPORTED_FLOORS]
    return cols
