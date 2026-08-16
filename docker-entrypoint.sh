#!/usr/bin/env bash
# RealEstateAI 容器启动脚本
# 作用：在带数据但缺模型产物时自动训练，使镜像在「有数据」前提下自洽可用；
#       无数据时给出清晰告警，避免 /api/predict/price 静默 503。
set -e

print_frontend_hint() {
  echo ""
  echo "============================================================"
  echo "  ✅ RealEstateAI 后端已就绪 (http://localhost:8000)"
  echo "------------------------------------------------------------"
  echo "  📊 API 文档:   http://localhost:8000/docs"
  echo ""
  echo "  🖥️  打开前端（在本机另开一个终端执行）:"
  echo "       cd frontend"
  echo "       npm run dev"
  echo "       然后浏览器打开:  http://localhost:5173"
  echo "  （前端已自动连接本机 8000 端口的后端，无需额外配置）"
  echo "============================================================"
  echo ""
}

print_nlp_hint() {
  # 运行时检测 NLP 语义模型是否可用，动态给出「已启用」或「如何启用」说明
  if python -c "import sentence_transformers" >/dev/null 2>&1; then
    echo "------------------------------------------------------------"
    echo "  🤖 NLP 语义分析：已启用（已安装 sentence-transformers）"
    echo "------------------------------------------------------------"
    return
  fi
  echo ""
  echo "------------------------------------------------------------"
  echo "  🤖 NLP 文本分析（虚假宣传检测 / 语义相似度）当前为「降级模式」"
  echo "     原因：精简镜像未包含 sentence-transformers + torch（约 +1.5GB）。"
  echo "     影响：仅 /api/analyze/text 不可用；价格 / 趋势 / 房源 / 宏观 /"
  echo "           城市对比 / AI 问答(RAG) 等核心功能均正常。"
  echo ""
  echo "     👉 若要启用 NLP 文本分析，请按以下步骤："
  echo "        1) 编辑 requirements-api.txt，取消注释下面两行依赖："
  echo "             torch==2.5.1"
  echo "             sentence-transformers==3.3.1"
  echo "             transformers==4.46.3"
  echo "             huggingface-hub==0.26.2"
  echo "        2) 重新构建并启动镜像（首次会下载模型 ~470MB，请耐心等待）："
  echo "             docker compose up --build --no-cache"
  echo "------------------------------------------------------------"
  echo ""
}

echo "🚀 RealEstateAI 启动检查..."

if [ -f data/realestate.db ]; then
  if [ ! -f models/xgb_model.pkl ] || [ ! -f models/rf_model.pkl ] || [ ! -f models/blend_model.pkl ]; then
    echo "🔧 检测到数据库但价格模型缺失，自动训练..."
    python models/train.py || echo "⚠️ 价格模型训练失败，/api/predict/price 将返回 503"
  fi
  if [ ! -f models/trend_model.pkl ]; then
    echo "🔧 自动拟合趋势模型..."
    python -c "from models.trend_predictor import TrendPredictor; p=TrendPredictor(); p.fit_all_cities(); p.save_model()" \
      || echo "⚠️ 趋势模型拟合失败，/api/predict/city_trend 将不可用"
  fi
  echo "✅ 数据与模型就绪"
else
  echo "⚠️ 未找到 data/realestate.db：价格/趋势预测将不可用。"
  echo "   请按 DEPLOY.md「三、数据与模型」准备数据后重启容器。"
fi

print_frontend_hint

print_nlp_hint

exec uvicorn api.main:app --host 0.0.0.0 --port 8000
