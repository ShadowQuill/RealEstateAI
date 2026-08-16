# RealEstateAI 后端 API 镜像
# 仅包含核心 API 服务（FastAPI + 价格/趋势预测 + 房源/指数接口）。
# NLP 语义分析依赖（torch 等）未安装，缺失时 /api/analyze/* 会自动降级，
# 不影响价格/趋势/房源等核心接口。

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_ENDPOINT=https://hf-mirror.com

# 先装依赖（利用层缓存）
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 再复制源码（含 data/ 数据库与 models/ 训练产物，若本地已存在）
COPY . .

# 赋予启动脚本可执行权限
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# 启动前先自检：带数据但缺模型时自动训练，使镜像自洽（详见 docker-entrypoint.sh）。
ENTRYPOINT ["./docker-entrypoint.sh"]
