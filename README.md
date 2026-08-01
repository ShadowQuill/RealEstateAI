# 🏡 中国城市房地产AI分析平台

基于机器学习的房地产数据分析平台，提供房价预测、文本智能分析、数据可视化等功能。

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| **房价预测** | 输入房屋特征（面积、年份、城市、户型、楼层），预测二手房总价 |
| **文本分析** | 从房产文本中自动提取成交价格，检测虚假宣传风险 |
| **数据可视化** | 交互式看板展示房价趋势、城市对比等分析结果 |
| **数据采集** | 链家房产数据爬虫，自动抓取房源信息 |

## 🛠️ 技术栈

| 模块 | 技术 |
|------|------|
| Web框架 | FastAPI + Uvicorn |
| 机器学习 | XGBoost + 随机森林 + 融合模型（Blending） |
| 数据处理 | pandas + numpy + scikit-learn |
| NLP引擎 | Transformers + Sentence-Transformers |
| 可视化 | Plotly + Dash |
| 数据库 | SQLite + SQLAlchemy |
| 爬虫 | Requests + BeautifulSoup4 |

## 📁 项目结构

```
RealEstateAI/
├── run_system.py              # 一键启动入口
├── requirements.txt           # 依赖清单
├── .env                       # 环境配置（API地址、端口等，不提交到仓库）
│
├── api/                       # FastAPI 后端接口
│   └── main.py                #   API主程序
│
├── dashboard/                 # 可视化看板
│   └── app.py                 #   Dash看板
│
├── scrapers/                  # 数据爬虫
│   └── lianjia_spider.py      #   链家爬虫
│
├── data_pipeline/             # 数据处理
│   └── feature_engineering.py #   特征工程
│
├── models/                    # 模型文件
│   ├── train.py               #   训练脚本
│   └── *.pkl                  #   模型文件
│
├── nlp_module/                # NLP模块
│   └── ai_analyzer.py         #   AI分析器
│
├── utils/                     # 工具
│   └── database.py            #   数据库配置
│
├── data/                      # 数据存放目录
│
├── log/                       # 日志目录
│   └── dashboard_debug.log    #   看板调试日志
│
└── cache/                     # NLP模型缓存
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

项目根目录下的 `.env` 文件用于配置服务地址和端口：

```ini
# API 服务配置
API_BASE_URL=http://127.0.0.1:8000
API_HOST=127.0.0.1
API_PORT=8000

# 看板配置
DASHBOARD_PORT=8050
```

> 使用默认值时无需修改，需要变更时编辑 `.env` 文件即可，无需改动代码。

### 3. 启动服务

```bash
# 方式一：一键启动（API + 看板）
python run_system.py

# 方式二：单独启动
python api/main.py          # 启动API服务
python dashboard/app.py     # 启动可视化看板
```

### 4. 访问服务

| 服务 | 地址 |
|------|------|
| API接口文档 | http://127.0.0.1:8000/docs |
| 健康检查 | http://127.0.0.1:8000/health |
| 可视化看板 | http://127.0.0.1:8050 |

## 📡 API接口说明

### 房价预测 `POST /predict`

输入房屋特征，返回预测价格。

**请求示例：**

```json
{
    "year": 2026,
    "area": 90.0,
    "building_year": 2015,
    "city_北京": 1,
    "city_上海": 0,
    "city_广州": 0,
    "city_深圳": 0,
    "layout_2室1厅": 0,
    "layout_3室1厅": 1,
    "layout_3室2厅": 0,
    "floor_info_低楼层": 0,
    "floor_info_中楼层": 0,
    "floor_info_高楼层": 1
}
```

**响应示例：**

```json
{
    "predicted_price": 456.78,
    "unit": "万元"
}
```

### 文本分析 `POST /analyze/text`

输入房产描述文本，提取价格并检测虚假宣传。

### 健康检查 `GET /health`

检查服务和模型加载状态。

## 🧠 模型说明

房价预测采用 **Blending 融合策略**：

```
输入特征 → XGBoost 预测 ──┐
                           ├→ 线性回归融合 → 最终价格
输入特征 → 随机森林 预测 ──┘
```

- 第一层：XGBoost 和随机森林分别预测
- 第二层：线性回归学习如何综合两个模型的结果

## 📊 数据流程

```
链家爬虫 → SQLite数据库 → 特征工程 → 模型训练 → API服务
                                    ↓
                              独热编码
                              数据标准化
                              特征列保存
```

## 📝 依赖说明

| 依赖 | 用途 |
|------|------|
| fastapi | Web API 框架 |
| uvicorn | ASGI 服务器 |
| pydantic | 数据校验 |
| scikit-learn | 机器学习工具 |
| xgboost | XGBoost 模型 |
| pandas | 数据处理 |
| transformers | NLP 模型 |
| dash + plotly | 可视化看板 |
| sqlalchemy | 数据库 ORM |
| python-dotenv | 环境变量配置 |
| beautifulsoup4 | 网页解析 |

## 👤 作者

- **hefeiyu**
- Email: 1340863075@qq.com

## 📄 许可证

本项目仅供学习参考使用。
