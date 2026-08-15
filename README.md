# RealEstateAI - 房地产 AI 分析系统

> **项目简介**：房地产 AI 分析系统：二手房价格预测、城市房价趋势研判与 AI 房源文本分析（54 城 + 国家统计局 70 城房价指数）

> **Topics**：real-estate, house-price-prediction, machine-learning, xgboost, random-forest, time-series-forecast, trend-analysis, nlp, chinese-nlp, data-analysis, playwright, fastapi, react, dashboard

<p align="center">
  <img src="docs/social_preview.png" alt="RealEstateAI 封面" width="100%"/>
</p>

RealEstateAI 是一个完整的房地产 AI 分析系统，覆盖**数据采集 → 价格预测 → 趋势预测 → AI 智能分析**全链路，并提供 **React 前端**的可视化界面。系统支持 **54 个城市**（基于链家/贝壳二手房数据 + 国家统计局 70 城房价指数），能够：

- 预测二手房总价与单价（机器学习模型，含装修 / 朝向特征）
- 预测城市房价未来趋势（多数据源时间序列模型：真实成交 / 官方指数折算 / 邻城指数代理）
- 对房源描述进行 AI 文本分析：成交价提取、虚假宣传检测、区域识别、情感分析
- 在新房价格指数、二手房房源、价格预测、榜单看板、AI 分析等页面中可视化城市房价、价格分布、性价比榜单等

---

## 系统架构

```
数据采集层      scrapers/（链家/贝壳爬虫 + 浏览器自动化成交抓取 + 指数/数据集导入）
数据处理层      data_pipeline/feature_engineering.py
模型层          models/train.py (价格) / models/trend_predictor.py (趋势)
服务层          api/ (FastAPI 接口)
展示层          frontend/ (React + Vite + Tailwind CSS + Recharts + Radix UI)
AI 分析层       nlp_module/ai_analyzer.py (SentenceTransformer 语义模型)
```

数据流向：**爬虫 / 导入 → SQLite（data/realestate.db）→ 特征工程 → 模型训练 → API → 前端展示**。

---

## 功能特性

1. **多城市数据采集**：内置 **54 个城市**，链家/贝壳双平台爬虫；并提供基于浏览器登录态（Cookie）的成交抓取脚本（绕过反爬）、国家统计局 70 城房价指数导入。真实请求失败时自动回退到内置模拟数据，保证离线可运行。
2. **价格预测**：XGBoost + RandomForest + 加权融合模型，输入城市、面积、户型、楼层、建成年份、**装修、朝向**等，输出单价与总价预测（融合 R² ≈ 0.65）。
3. **趋势预测**：多项式回归时间序列模型，按城市数据源分四类拟合（详见「数据来源」）；
   - 真实成交：多年份真实成交均价直接按年聚合；
   - 官方指数折算：单年城市以该年真实成交均价为锚，按统计局二手住宅同比指数链式折算近 10 年；
   - 邻城指数代理：不在 70 城样本内的单年城市（中山、苏州、保定、廊坊、绍兴、芜湖、镇江、潍坊、泰州等共 15 城），借用邻近大城市官方同比指数折算历年价格水平；
   - 真实成交（单年）：极少数无邻城 / 官方指数可折算时的兜底，置信度最低。
4. **AI 文本分析**：基于 `sentence-transformers`（paraphrase-multilingual-MiniLM-L12-v2）语义模型，支持成交价提取、虚假宣传检测（语义相似度 + 关键词库）、区域/特征提取、情感分析等能力。
5. **现代前端**：React + Vite + Tailwind CSS + Recharts + Radix UI 构建的响应式界面，含 **6 个页面**——城市房源列表、房源详情、新房价格指数、价格预测、榜单看板、AI 分析。

---

## 项目结构

完整目录说明见 [`menu.txt`](./menu.txt)。核心目录如下：

```
api/               FastAPI 后端（路由、预测、分析、NLP 接口）
models/            模型训练脚本与训练产物（*.pkl）
nlp_module/        AI 文本分析模块（SentenceTransformer）
data_pipeline/     特征工程
scrapers/          链家/贝壳爬虫、浏览器成交抓取、指数/数据集导入
utils/            数据库、常量、文本处理等工具
frontend/         React 前端（含 dist/ 构建产物）
data/             运行时 SQLite 数据库
run_system.py     一键启动脚本（API + 看板 + 前端）
run_update.py     数据更新（爬取 + 训练）脚本
run_update_real.py 保留现有真实数据重训价格/趋势模型
.env              运行配置（端口、HF 镜像源）
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> 说明：`torch`、`transformers`、`sentence-transformers` 体积较大；NLP 语义模型（paraphrase-multilingual-MiniLM-L12-v2）首次运行时会自动下载至 `cache/` 目录。项目已通过 `.env` 中的 `HF_ENDPOINT=https://hf-mirror.com` 配置国内镜像以加速拉取。

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
python run_system.py --with-frontend
```

该脚本会：
- 初始化数据库；
- 若缺少模型文件（`xgb_model.pkl` / `rf_model.pkl` / `blend_model.pkl` / `trend_predictor.pkl`）则自动训练；
- 启动 FastAPI 后端（默认 `http://127.0.0.1:8000`）；
- 启动 Dash 看板（默认 `http://127.0.0.1:8050`）；
- **`--with-frontend` 一并启动 React 前端**（开发模式 `http://localhost:5173`）。

常用参数：

| 参数 | 说明 |
|------|------|
| `--with-frontend` | 一键拉起 后端 + 看板 + 前端（不加则只起后端与看板，前端需手动 `cd frontend && npm run dev`） |
| `--stop` | 干净停止全部相关服务（按端口精确 kill，含残留的管理主进程） |
| `--no-autokill` | 端口被占用时**不**自动释放占用进程（默认会自动 kill 占用者再启动） |

> 启动完成后，输出会以醒目方式标出前端地址（`http://localhost:5173`），即网页界面入口。
> 端口被占用时会自动终止占用进程；如需在新实例中重新接管，新 `run_system.py` 启动时会先停掉旧的管理主进程。

前端独立开发预览也可：

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

### 4. 更新数据与模型

```bash
python run_update_real.py
```

在保留现有真实数据的前提下重新训练价格与趋势模型。

> ⚠️ `run_update.py` 会先清空 `houses` 表再爬取，当前库内的真实成交数据会被
> 抓不到数据时的模拟回退覆盖。除非确实要重建整个数据集，否则请使用
> `run_update_real.py`。

### 5. 浏览器自动化抓取成交（需登录态）

贝壳 / 链家对无登录态请求有反爬限制，建议使用浏览器 Cookie 抓取：

```bash
# 1) 用浏览器手动登录链家后导出 Cookie（弹出 Chrome，登录后回车导出）
python scrapers/save_cookies.py
# 2) 用 Cookie 抓取成交（有头模式 + --human 遇验证码可手动过）
python scrapers/chengjiao_browser.py --cities 中山 --human --pages 3
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--start-page N` | 起始页（默认 1）；扩量重跑设 4 可跳过已抓页、避免重复触发验证码 |
| `--fast` | 快速模式：页间 8–15s→2–4s、城间 5–10s→2–3s（换新号/赶进度时用，封号风险略增） |
| `--area AREA` | 按区域/街道细分（如 `chancheng`/`nanhai`/`shunde`）突破单城 100 页上限，深翻到历史年份 |
| `--year/--sdate/--bdate` | 限定成交年份或日期范围；链家成交页已证实**忽略**这些 query 参数，请改用 `--area` 深翻 |

> ⚠️ 大量历史成交链家公开显示「暂无价格」（数据策略，非爬虫 bug），抓到的 `price=NULL` 行对价格模型无贡献，会被清理。

Cookie 存于 `data/raw/lianjia_cookies.json`（已被 `.gitignore` 忽略）。

---

## 数据来源

当前数据库为真实数据，不含任何模拟或合成房源；房价指数来自国家统计局 70 城样本。

**54 城市按趋势数据源分为三类**（接口通过 `data_source` 字段标明，另有单年兜底）：

- `真实成交`：房源覆盖多个年份时，直接按年聚合真实成交均价（如北京 2010–2018）。
- `官方指数折算`：房源仅覆盖单一年份且该城在统计局 70 城样本内时，以该年真实成交均价为锚点，按二手住宅同比指数链式折算近 10 年价格水平。
- `邻城指数代理`：房源仅覆盖单一年份且本城不在 70 城样本内时（如中山、苏州、保定、廊坊、绍兴、芜湖、镇江、潍坊、泰州等共 15 城），借用邻近大城市（同城市群、走势相关）的官方同比指数代为折算历年价格水平。方向由真实官方指数驱动，但绝对价格水平是缩放近似，故置信度低于前两类。
- `真实成交（单年）`：极少数无邻城 / 官方指数可折算时的兜底，仅保留单年快照。

另有 `city_index` 表存放国家统计局 70 城房价指数，覆盖 70 城、2006–2026 年新房与二手房的同比 / 环比 / 定基比指数。

年成交样本少于 30 条的年份均价不具统计意义，已从趋势拟合与走势接口中排除。

---

## API 接口

后端默认地址 `http://127.0.0.1:8000`，主要接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/health` | 健康检查 / 模型加载状态 |
| GET  | `/api/cities` | 支持的城市列表（含统计） |
| GET  | `/api/cities/{city}/listings` | 城市房源列表（分页、排序、筛选） |
| GET  | `/api/cities/{city}/stats` | 城市统计（房源数、均价、分布等） |
| GET  | `/api/listings/{listing_id}` | 房源详情（含同小区房源） |
| POST | `/api/predict/price` | 给定完整特征（含装修/朝向）预测总价 |
| GET  | `/api/predict/city_trend/{city}` | 城市历史趋势与未来 N 年预测（含数据源） |
| POST | `/api/predict/listing_future` | 单房源未来价格预测 |
| GET  | `/api/index/cities` | 70 城房价指数城市列表 |
| GET  | `/api/index/city/{city}` | 指定城市历年新房/二手房指数 |
| GET  | `/api/index/compare` | 多城指数对比 |
| GET  | `/api/config/predict` | 价格预测可选配置（户型/装修/朝向等） |
| POST | `/api/analyze/text` | NLP 文本分析（价格提取、虚假宣传检测等） |
| POST | `/api/analyze/listing/{listing_id}` | 分析指定房源描述文本 |
| GET  | `/api/dashboard/overview` | 仪表盘总览数据 |
| GET  | `/api/dashboard/yearly_trend` | 年度价格走势 |

> 路由名以 `api/main.py` 实际注册为准。

---

## 模型说明

- **价格预测模型**（`models/train.py`）：以城市、面积、房龄、户型、楼层、**装修、朝向**等特征训练 XGBoost 与 RandomForest，再做加权融合（`blend_model.pkl`）。特征标准化器 `scaler.pkl` 与特征列顺序 `feature_cols.pkl` 与 API 端严格一致。
- **趋势预测模型**（`models/trend_predictor.py`）：对每个城市按年份聚合均价，使用二次多项式回归拟合趋势，预测未来房价与年化增长率，保存为 `trend_predictor.pkl`；按城市可用数据在「真实成交 / 官方指数折算 / 邻城指数代理 / 单年兜底」四类数据源间自动路由。
- **AI 分析模型**（`nlp_module/ai_analyzer.py`）：基于 `sentence-transformers` 加载 `paraphrase-multilingual-MiniLM-L12-v2` 模型，结合正则匹配进行成交价/单价提取、语义相似度虚假宣传检测、区域与特征提取、情感分析，生成综合分析报告。

### 各城训练样本量与准确性档位

价格预测模型（融合 R² ≈ 0.65）的训练集由「内置 CSV 历史数据 + 浏览器抓取的链家成交」共同构成。54 城的**有价成交样本量极度不均**，直接决定各城价格预测的可靠性。库内当前有价样本分布（部分城市样例）：

| 档位 | 城市 | 有价样本量 | 价格预测可靠性 |
|------|------|-----------|---------------|
| **精确（强）** | 北京 | ~311,000 | ✅ 极高 |
| | 成都 | ~116,000 | ✅ 极高 |
| | 上海 | ~90,000 | ✅ 极高 |
| **较准（中）** | 中山 | 2,317 | ✅ 高 |
| | 潍坊 | 598 | ✅ 可用 |
| | 保定 | 483 | ✅ 可用 |
| | 珠海 | 295 | ✅ 可用 |
| **粗略（弱）** | 其余 46 城（含东莞、佛山、苏州、昆山、南通、嘉兴、廊坊、绍兴、芜湖、镇江 等新抓城市） | 每城 30–37 | ⚠️ 仅能粗略估计 |

**关键说明：**

- **整体 R² ≈ 0.65 主要由北京 / 成都 / 上海三大样本池（占全库 99% 以上）驱动**；这三个核心城市的价格预测已相当精确，是产品主力能力。
- **弱样本档位（46 城，每城约 30 条）是产品的「最小样本基线」**，并非漏抓。这些城市多为二三线及新城，链家对大量历史成交**公开显示「暂无价格」**（数据策略，非爬虫 bug），故可获取的有价成交天然稀少。
- **趋势预测不受样本量限制**：趋势模型使用国家统计局 70 城房价指数（每城 10 年），与成交样本量无关，54 城趋势判断天然准确。
- **补充成交价对弱样本档位无实质提升**：对东莞 / 佛山 / 苏州等不公开成交价的城市，反复爬取得到的仍是 `price=NULL` 的废料；要提升这些城市的价格预测，唯一出路是用**在售页 `ershoufang` 挂牌价近似**（挂牌价 ≠ 成交价，会引入系统性偏差，默认不启用）。

---

## 技术栈

- **后端**：FastAPI、SQLAlchemy、pandas、scikit-learn、XGBoost
- **数据采集**：requests、BeautifulSoup、lxml、Playwright（浏览器成交抓取）、Playwright（浏览器成交抓取）
- **可视化**：Dash、Plotly
- **前端**：React、Vite、Tailwind CSS、Recharts、Radix UI
- **NLP**：sentence-transformers

---

## 注意事项

- 爬虫真实请求可能受反爬限制，失败时会回退到内置模拟数据。当前库内为真实数据，
  运行爬虫前请留意回退行为，避免模拟数据混入（详见「数据来源」）。
- 浏览器成交抓取（`scrapers/chengjiao_browser.py`）依赖 `data/raw/lianjia_cookies.json`
  中的登录态 Cookie；频繁深抓会触发账号临时封禁，请控制抓取节奏。
- NLP 语义模型首次运行时会自动下载（约 120MB），之后缓存于 `cache/` 目录。
- 前端 `PricePredictPage.tsx` 中的城市/户型/楼层/装修/朝向列表需与
  `utils/constants.py` 保持一致，变更需重新训练模型。
- `data/realestate.db`（约 270MB）为可再生运行数据，已被 `.gitignore` 忽略，不纳入版本控制。
