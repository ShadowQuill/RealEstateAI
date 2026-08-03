# 🏡 RealEstateAI — 中国城市房地产 AI 分析平台

基于机器学习的房地产数据分析平台，提供房价预测、文本智能分析、趋势预测、数据可视化等功能。

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 城市房源浏览 | 查看所有城市的房源数据，支持分页、排序、价格/面积筛选 |
| 趋势预测 | 选择单条房源，基于历史数据预测未来 1-20 年的价格走势 |
| 房价预测 | 输入房屋特征（面积、年份、城市、户型、楼层），预测二手房总价 |
| NLP 文本分析 | 从房产文本中自动提取成交价、识别区域、检测虚假宣传、情感分析 |
| 数据可视化 | 交互式仪表盘展示房价趋势、城市对比、价格-面积散点图 |
| 数据采集 | 链家 + 贝壳二手房真实数据爬虫，覆盖 29 个中国城市 |

## 🛠️ 技术栈

| 模块 | 技术 |
|------|------|
| 前端框架 | React 19 + TypeScript + Vite |
| UI 框架 | Tailwind CSS 3 + shadcn/ui (Radix UI) |
| 图表库 | Recharts（前端）/ Plotly Dash（传统看板） |
| Web 框架 | FastAPI + Uvicorn |
| 机器学习 | XGBoost + 随机森林 + Blending 融合模型 |
| 趋势预测 | 线性回归 + 多项式拟合 |
| 数据处理 | pandas + numpy + scikit-learn |
| NLP 引擎 | Transformers + Sentence-Transformers |
| 数据库 | SQLite + SQLAlchemy |
| 爬虫 | Requests + BeautifulSoup4 |

## 📁 项目结构

```
RealEstateAI/
├── run_system.py              # 一键启动入口（API + Dash看板）
├── run_update.py              # 一键数据更新（爬取 + 训练）
├── requirements.txt           # Python 依赖清单
├── .env                       # 环境配置
│
├── api/                       # FastAPI 后端接口
│   └── main.py                #   房源查询、趋势预测、NLP分析
│
├── frontend/                  # React 前端应用
│   └── src/
│       ├── components/        #   通用组件（导航栏等）
│       ├── sections/          #   页面组件
│       │   ├── DashboardPage.tsx        # 数据仪表盘
│       │   ├── CityListingsPage.tsx     # 城市房源列表
│       │   ├── ListingDetailPage.tsx    # 房源详情 + 趋势预测
│       │   └── NLPAnalysisPage.tsx      # NLP 文本分析
│       ├── types/api.ts       #   TypeScript 类型 + API 封装
│       └── lib/               #   工具函数
│
├── dashboard/                 # Plotly Dash 可视化看板（传统版）
│   └── app.py
│
├── scrapers/                  # 数据爬虫
│   └── lianjia_spider.py      #   链家/贝壳二手房爬虫（29个城市）
│
├── data_pipeline/             # 数据处理
│   └── feature_engineering.py #   特征工程
│
├── models/                    # 模型文件
│   ├── train.py               #   房价预测模型训练
│   ├── trend_predictor.py     #   趋势预测模型
│   └── *.pkl                  #   训练好的模型文件
│
├── nlp_module/                # NLP 模块
│   └── ai_analyzer.py         #   文本分析引擎
│
├── utils/                     # 工具
│   └── database.py            #   数据库 ORM 模型
│
├── data/                      # 数据目录
│   └── realestate.db          #   SQLite 数据库
│
├── log/                       # 日志
└── cache/                     # NLP 模型缓存
```

## 🚀 快速开始

### 1. 环境准备

**Python 后端：**

```bash
# 安装 Python 依赖
pip install -r requirements.txt
```

**React 前端（需要 Node.js 18+）：**

```bash
cd frontend
npm install
```

### 2. 初始化数据（首次运行）

```bash
# 一键数据更新：爬取真实房源 → 生成历史数据 → 训练模型
python run_update.py
```

此命令会自动完成：
- 从链家和贝壳爬取北京、上海、广州、深圳等 29 个城市的真实房源数据
- 生成 2022-2025 年的历史趋势数据
- 训练 XGBoost + 随机森林房价预测模型
- 训练各城市趋势预测模型

### 3. 启动服务

**方式一：一键启动（推荐）**

打开两个终端：

```bash
# 终端 1：启动后端（API + Dash 看板）
python run_system.py
```

```bash
# 终端 2：启动前端开发服务器
cd frontend
npm run dev
```

**方式二：分别启动**

```bash
# 启动 API 服务
python api/main.py

# 启动 Dash 看板（可选）
python dashboard/app.py

# 启动前端（新终端）
cd frontend && npm run dev
```

### 4. 访问服务

| 服务 | 地址 |
|------|------|
| **前端主页** | http://localhost:5173 |
| API 接口文档 (Swagger) | http://127.0.0.1:8000/docs |
| 健康检查 | http://127.0.0.1:8000/health |
| Dash 可视化看板 | http://127.0.0.1:8050 |

### 5. 功能页面说明

| 页面 | 路由 | 功能 |
|------|------|------|
| 数据仪表盘 | `/` | 房源总览、城市房价排行、装修分布、价格-面积散点图 |
| 城市房源 | `/city/:cityName` | 按城市浏览房源，支持分页、排序、价格/面积筛选 |
| 房源详情 | `/predict/:id` | 查看房源详细信息，**预测未来 1-20 年价格趋势** |
| NLP 分析 | `/nlp` | 输入房产文本，提取成交价、识别区域、检测虚假宣传、情感分析 |

### 6. 数据更新

```bash
# 清空旧数据 → 重新爬取 → 重新训练所有模型
python run_update.py

# 或仅爬虫
python scrapers/lianjia_spider.py

# 或仅训练预测模型
python models/train.py
```

## 📡 核心 API 接口

### 城市房源列表 `GET /api/cities/{city}/listings`

支持分页、排序、价格和面积筛选。

```
GET /api/cities/北京/listings?page=1&page_size=20&sort_by=price&sort_order=desc&min_price=100&max_price=1000
```

### 房源未来趋势预测 `POST /api/predict/listing_future`

```json
// 请求
{ "city": "北京", "current_price": 500, "area": 89, "future_years": 5 }

// 响应示例
{
  "city": "北京",
  "current_price": 500.0,
  "predictions": [
    { "year": 2027, "predicted_price": 537.75, "yoy_growth": 7.55 },
    { "year": 2028, "predicted_price": 580.50, "yoy_growth": 7.95 },
    ...
  ],
  "total_growth": 36.15
}
```

### NLP 文本分析 `POST /api/analyze/text`

输入房产描述文本，自动提取成交价、识别区域、检测虚假宣传风险、分析情感倾向。

### 城市趋势预测 `GET /api/predict/city_trend/{city}?future_years=5`

获取指定城市未来 N 年的平均房价趋势。

### 其他接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/cities` | 所有城市及统计 |
| GET | `/api/cities/{city}/stats` | 城市详细统计（区域、户型、装修分布） |
| GET | `/api/listings/{id}` | 房源详情 + 同小区房源 |
| POST | `/api/analyze/listing/{id}` | 分析指定房源描述 |
| GET | `/api/dashboard/overview` | 仪表盘总览数据 |
| GET | `/api/dashboard/yearly_trend` | 年度房价走势 |

## 🧠 模型说明

### 房价预测模型（Blending 融合）

```
输入特征 → XGBoost 预测 ──┐
                           ├→ 线性回归融合 → 最终价格
输入特征 → 随机森林 预测 ──┘
```

### 趋势预测模型

基于每个城市的历史年份数据，采用线性回归 + 多项式组合拟合，外推未来 1-20 年的价格走势。支持按面积系数调整预测值。

## 📊 数据流程

```
链家/贝壳真实数据 → SQLite数据库 → 特征工程 → 模型训练
                                         ↓
                                   独热编码 + 标准化
                                         ↓
                                   API服务 ← 模型文件(.pkl)
                                         ↓
                              React前端 / Dash看板 / Swagger文档
```

## 📝 依赖说明

| 依赖 | 用途 |
|------|------|
| fastapi + uvicorn | Web API 框架 + ASGI 服务器 |
| scikit-learn + xgboost | 机器学习模型 |
| pandas + numpy | 数据处理 |
| sentence-transformers | NLP 语义分析 |
| requests + beautifulsoup4 | 网页爬虫 |
| sqlalchemy | 数据库 ORM |
| python-dotenv | 环境变量管理 |
| React + Vite + TypeScript | 前端框架 |
| Tailwind CSS + shadcn/ui | UI 组件库 |
| Recharts | 前端图表 |
| Plotly + Dash | 传统可视化看板 |

## 👤 作者

- **hefeiyu**
- Email: 1340863075@qq.com

## 📄 许可证

本项目仅供学习参考使用。
