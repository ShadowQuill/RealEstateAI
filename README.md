# RealEstateAI - 房地产 AI 分析系统

RealEstateAI 是一个完整的房地产 AI 分析系统，覆盖**数据采集 → 价格预测 → 趋势预测 → AI 智能分析**全链路，并提供 **Flask 看板 + React 前端**的可视化界面。系统支持 30 个城市（基于链家/贝壳二手房数据），能够：

- 预测二手房总价与单价（机器学习模型）
- 预测城市房价未来趋势（时间序列模型）
- 通过自然语言提问，由本地大模型（GLM-4-9B）+ RAG 给出分析报告
- 在看板与前端中可视化城市房价、价格分布、性价比榜单等

---

## 系统架构

```
数据采集层      scrapers/lianjia_spider.py  →  SQLite (data/realestate.db)
数据处理层      data_pipeline/feature_engineering.py
模型层          models/train.py (价格) / models/trend_predictor.py (趋势)
服务层          api/ (FastAPI 接口) + dashboard/ (Flask 看板)
展示层          frontend/ (React + Vite + Ant Design) / dashboard 模板
AI 分析层       nlp_module/ai_analyzer.py (本地大模型 + RAG)
```

数据流向：**爬虫 → 数据库 → 特征工程 → 模型训练 → API/看板/前端展示**。

---

## 功能特性

1. **多城市数据采集**：内置 30 个城市，链家/贝壳双平台爬虫；真实请求失败时自动回退到内置模拟数据，保证离线可运行。
2. **价格预测**：XGBoost + RandomForest + 加权融合模型，输入城市、面积、户型、楼层、建成年份等，输出单价与总价预测。
3. **趋势预测**：多项式回归时间序列模型，基于 2022–2024 历史均价拟合，预测城市未来房价走势与年化增长率。
4. **AI 智能分析**：基于本地部署的 `THUDM/glm-4-9b-chat` 大模型，支持意图识别、数据检索增强（RAG）与示例引导，生成自然语言分析报告（支持中文问答）。
5. **可视化看板**：Flask + Plotly 看板，展示城市均价、价格分布、户型/面积统计、性价比榜单、趋势曲线。
6. **现代前端**：React + Vite + Ant Design + Tailwind CSS 构建的响应式界面，与后端 API 联动。

---

## 项目结构

完整目录说明见 [`menu.txt`](./menu.txt)。核心目录如下：

```
api/               FastAPI 后端（路由、预测、分析、NLP 接口）
models/            模型训练脚本与训练产物（*.pkl）
nlp_module/        AI 分析模块（本地大模型实现）
data_pipeline/     特征工程
scrapers/          链家/贝壳爬虫
utils/            数据库、常量、文本处理等工具
dashboard/        Flask 可视化看板
frontend/         React 前端（含 dist/ 构建产物）
data/             运行时 SQLite 数据库
run_system.py     一键启动脚本
run_update.py     数据更新（爬取 + 训练）脚本
.env              运行配置（端口、HF 镜像源）
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> 说明：`torch`、`transformers` 体积较大；AI 问答依赖 `THUDM/glm-4-9b-chat` 模型权重（已下载至本地 `models/glm4` 目录）。若需重新下载，项目已通过 `.env` 中的 `HF_ENDPOINT=https://hf-mirror.com` 配置国内镜像以加速拉取。

### 2. 配置（可选）

编辑 `.env` 调整端口与镜像源：

```
API_HOST=127.0.0.1
API_PORT=8000
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=8050
HF_ENDPOINT=https://hf-mirror.com
```

### 3. 运行完整系统

```bash
python run_system.py
```

该脚本会：
- 初始化数据库；
- 若缺少模型文件（`xgb_model.pkl` / `rf_model.pkl` / `blend_model.pkl` / `trend_predictor.pkl`）则自动训练；
- 启动 FastAPI 后端（默认 `http://127.0.0.1:8000`）；
- 启动 Flask 看板（默认 `http://127.0.0.1:8050`）；
- 构建并预览 React 前端（开发模式 `http://localhost:5173`，生产静态文件由 API 挂载）。

### 4. 更新数据与模型

```bash
python run_update.py
```

将重新爬取房源、生成 2022–2024 历史数据、训练价格与趋势模型。

---

## API 接口

后端默认地址 `http://127.0.0.1:8000`，主要接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/` | 健康检查 / API 说明 |
| GET  | `/api/cities` | 支持的城市列表 |
| GET  | `/api/stats/:city` | 城市统计（房源数、均价、面积分布等） |
| POST | `/api/predict` | 给定城市+面积+户型等参数，预测单价与总价 |
| POST | `/api/predict/price` | 给定完整特征直接预测总价 |
| GET  | `/api/trend/:city` | 城市历史趋势与未来 N 年预测 |
| GET  | `/api/ranking` | 城市房价/性价比榜单 |
| POST | `/api/analyze` | 自然语言分析（AI 问答，本地大模型 + RAG） |

> 路由名以 `api/main.py` 实际注册为准。

---

## 模型说明

- **价格预测模型**（`models/train.py`）：以城市、面积、房龄、户型、楼层等特征训练 XGBoost 与 RandomForest，再做加权融合（`blend_model.pkl`）。特征标准化器 `scaler.pkl` 与特征列顺序 `feature_cols.pkl` 与 API 端严格一致。
- **趋势预测模型**（`models/trend_predictor.py`）：对每个城市按年份聚合均价，使用二次多项式回归拟合趋势，预测未来房价与年化增长率，保存为 `trend_predictor.pkl`。
- **AI 分析模型**（`nlp_module/ai_analyzer.py`）：本地加载 `THUDM/glm-4-9b-chat`，结合数据库检索（RAG）与示例提示，生成分析报告。

---

## 技术栈

- **后端**：FastAPI、SQLAlchemy、pandas、scikit-learn、XGBoost、transformers / torch
- **数据采集**：requests、BeautifulSoup、lxml
- **可视化**：Flask、Plotly
- **前端**：React、Vite、Ant Design、Tailwind CSS、Axios
- **NLP**：Transformers、Jieba

---

## 注意事项

- 爬虫真实请求可能受反爬限制，系统已内置模拟数据回退，离线也能完整演示。
- AI 问答需要本地大模型权重（约数 GB），首次运行若缺失将自动尝试下载（受 `.env` 镜像源影响）。
- 项目为演示/学习用途，价格与趋势预测基于历史统计拟合，不构成任何投资或交易建议。
