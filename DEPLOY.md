# RealEstateAI 部署指南

把本地完整可运行的房地产 AI 系统部署到公网，拿到简历可贴的演示链接。

## 一、镜像包含什么

`Dockerfile` 构建的是**后端 API 服务**（FastAPI，端口 8000），覆盖：

- 城市房源查询、价格预测（`/api/predict/price`）、趋势预测（`/api/predict/city_trend`）
- 国家统计局 70 城房价指数、新房/二手房指数接口
- 仪表盘汇总接口
- 当前宏观环境接口（`/api/macro`：GDP/CPI/M2/PMI/利率快照 + 自动简评）

NLP 语义分析依赖（torch / sentence-transformers）**未装进镜像**，`/api/analyze/*` 在缺失时自动降级，不影响核心接口。

## 二、本地验证（Docker）

```bash
docker compose up --build      # 构建并启动，访问 http://localhost:8000/health
docker compose up -d           # 后台运行
docker compose down            # 停止
```

`docker-compose.yml` 通过绑定挂载共享本机 `data/` 与 `models/`，因此只要本机已跑过爬虫与训练，容器即可直接用现有数据库与模型产物。

## 三、重要前提：数据与模型不在 Git 里

`.gitignore` 忽略了两类大文件：

- `data/*.db`（约 304MB 真实房源库，由爬虫生成）
- `models/*.pkl`（训练产物，几 MB~几十 MB）

因此**从 GitHub 全新克隆不会包含它们**。云端从 Git 部署时会缺数据与模型。三种处理方案：

### 方案 A（推荐，最省心）：本地构建镜像 → 推 registry → 部署镜像

数据/模型已在本机，把整目录一起打进镜像后推送，云端直接用现成镜像，无需再爬数据/训练。

```bash
# 1) 本地构建（自动带入 data/ 与 models/）
docker build -t realestate-ai:latest .

# 2) 推送到 Docker Hub 或 GHCR
docker tag realestate-ai:latest <你的用户名>/realestate-ai:latest
docker push <你的用户名>/realestate-ai:latest

# 3) Railway / Render 选择「Deploy an existing image」，填入上面的镜像地址
```

### 方案 B：Git LFS 提交数据/模型后从 Git 部署

```bash
git lfs install
git lfs track "data/*.db" "models/*.pkl"
git add .gitattributes data/*.db models/*.pkl
git commit -m "chore: 用 LFS 纳入数据库与模型产物"
git push
```

然后 Railway / Render 从 GitHub 部署（用本仓库的 `Dockerfile`）。注意 DB 较大，LFS 有配额。

### 方案 C：云端首次运行时训练（无数据也能起服务）

镜像内 `api.main` 在趋势模型缺失时会**自动拟合**所有城市；价格模型缺失则 `/api/predict/price` 返回 503。
可在 Dockerfile 的 `CMD` 前加一步训练（需容器内先有数据）：

```dockerfile
RUN python models/train.py && python -c "from models.trend_predictor import TrendPredictor; p=TrendPredictor(); p.fit_all_cities(); p.save_model()"
```

但若容器里没有 `data/*.db`，训练无意义——此方案需配合"先导入数据"。

## 四、Railway 部署步骤

1. 注册 [Railway](https://railway.app)，New Project → Deploy from GitHub repo。
2. 若用方案 A：选择「Deploy from image」填入镜像地址；若用方案 B：选 GitHub 仓库，Railway 自动识别 `Dockerfile`。
3. 设置环境变量（可选）：`HF_ENDPOINT=https://hf-mirror.com`。
4. 生成域名（Railway 默认分配 `xxx.up.railway.app`），即为公网链接。
5. 验证：`https://<你的域名>/health` 应返回模型状态。

## 五、Render 部署步骤

1. 注册 [Render](https://render.com)，New → Web Service。
2. 连接 GitHub 仓库（方案 B）或选择「Existing Image」（方案 A，填镜像地址）。
3. Runtime 选 Docker，实例类型选免费/入门级。
4. 启动后 Render 分配 `https://<服务名>.onrender.com`。
5. 验证：`/health` 接口与前端联调。

## 六、前端看板（可选独立部署）

React 看板（端口 5173 / 构建产物 `frontend/dist`）建议单独部署到静态托管
（Vercel / Netlify / GitHub Pages），并将 API _BASE 指向上面的公网后端地址。
详见 `README.md`。

## 七、安全与成本提示

- 免费实例休眠后首次请求较慢（冷启动），属正常。
- 公网暴露的 API 当前为开放只读接口，演示用途足够；若上线真实数据，建议加鉴权与限流。
- 数据库为本地 SQLite，并发写入能力有限，演示足够；生产可换 Postgres。
