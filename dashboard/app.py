# dashboard/app.py
import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import pandas as pd
import requests
from sqlalchemy import create_engine
import os
import json
from datetime import datetime
import time

# ---------- 日志 ----------
LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'dashboard_debug.log')

def log_debug(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(full_msg + '\n')

if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)
log_debug("========== Dashboard 启动 ==========")

# ---------- 连接数据库 ----------
engine = create_engine("sqlite:///./data/realestate.db")

# ---------- 辅助函数：带重试的API调用 ----------
def call_api_with_retry(features, max_retries=2, timeout=3):
    """
    调用预测API，支持重试
    """
    url = 'http://127.0.0.1:8000/predict'
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, json=features, timeout=timeout)
            if resp.status_code == 200:
                return resp.json().get('predicted_price'), None
            else:
                return None, f"API返回 {resp.status_code}: {resp.text[:100]}"
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                log_debug(f"  请求超时，第 {attempt+1} 次重试...")
                time.sleep(0.5)
                continue
            else:
                return None, f"超时 (重试 {max_retries} 次)"
        except Exception as e:
            return None, str(e)
    return None, "未知错误"

# ---------- Dash 应用 ----------
app_dash = dash.Dash(__name__)

app_dash.layout = html.Div([
    html.H1("🏠 全国二手房数据看板（AI预测版）", style={'textAlign': 'center'}),
    dcc.Dropdown(
        id='city-filter',
        options=[{'label': c, 'value': c} for c in ['北京', '上海', '广州', '深圳']],
        value='北京'
    ),
    dcc.Graph(id='price-scatter'),
    dcc.Graph(id='prediction-vs-actual'),
    html.Div(id='status-message', style={'textAlign': 'center', 'color': 'gray'})
])

# ---------- 回调1：散点图 ----------
@app_dash.callback(
    Output('price-scatter', 'figure'),
    Input('city-filter', 'value')
)
def update_scatter(city):
    log_debug(f"散点图回调触发，城市={city}")
    df = pd.read_sql("SELECT * FROM houses", engine)
    df_filtered = df[df['city'] == city]
    if df_filtered.empty:
        log_debug(f"城市 {city} 无数据")
        return px.scatter(title=f'{city} 暂无数据')
    fig = px.scatter(df_filtered, x='area', y='price',
                     title=f'{city} 总价 / 面积',
                     labels={'area': '面积(㎡)', 'price': '总价(万元)'})
    return fig

# ---------- 回调2：预测对比图 ----------
@app_dash.callback(
    Output('prediction-vs-actual', 'figure'),
    Output('status-message', 'children'),
    Input('city-filter', 'value')
)
def update_prediction(city):
    log_debug(f"========== 预测回调触发，城市={city} ==========")

    df = pd.read_sql("SELECT * FROM houses", engine)
    df_city = df[df['city'] == city]
    if df_city.empty:
        log_debug(f"城市 {city} 无数据")
        return px.bar(title=f'{city} 暂无数据'), f'⚠️ 城市 {city} 无数据'

    layouts = df_city['layout'].dropna().unique()
    floors = df_city['floor_info'].dropna().unique()
    log_debug(f"数据库中的户型值: {layouts}")
    log_debug(f"数据库中的楼层值: {floors}")

    df_sample = df_city.head(10).copy()
    predictions = []
    api_ok = True
    error_msg = ""

    # 映射表
    layout_map = {
        '2室1厅': '2室1厅',
        '2室2厅': '2室1厅',
        '3室1厅': '3室1厅',
        '3室2厅': '3室2厅',
        '3室3厅': '3室2厅',
        '4室2厅': '3室2厅',
    }
    floor_map = {
        '低楼层': '低楼层',
        '低层': '低楼层',
        '中楼层': '中楼层',
        '中层': '中楼层',
        '高楼层': '高楼层',
        '高层': '高楼层',
    }

    for idx, row in df_sample.iterrows():
        log_debug(f"--- 处理第 {idx} 条数据 ---")

        # ---- 清洗数值 ----
        area_val = row['area']
        if pd.isnull(area_val) or area_val <= 0:
            area_val = 80.0
            log_debug(f"  面积无效，设为80")

        year_val = row['building_year']
        current_year = 2026
        if pd.isnull(year_val) or not (1900 <= year_val < current_year):
            year_val = 2000
            log_debug(f"  建成年份无效，设为2000")

        # ---- 清洗分类 ----
        layout_raw = str(row.get('layout', '')).strip()
        floor_raw = str(row.get('floor_info', '')).strip()
        layout_std = layout_map.get(layout_raw, '3室2厅')
        floor_std = floor_map.get(floor_raw, '中楼层')
        log_debug(f"  layout: '{layout_raw}' -> '{layout_std}', floor: '{floor_raw}' -> '{floor_std}'")

        # ---- 构造特征 ----
        features = {
            'area': float(area_val),
            'building_year': int(year_val),
            'layout_2室1厅': 1.0 if layout_std == '2室1厅' else 0.0,
            'layout_3室1厅': 1.0 if layout_std == '3室1厅' else 0.0,
            'layout_3室2厅': 1.0 if layout_std == '3室2厅' else 0.0,
            'floor_info_低楼层': 1.0 if floor_std == '低楼层' else 0.0,
            'floor_info_中楼层': 1.0 if floor_std == '中楼层' else 0.0,
            'floor_info_高楼层': 1.0 if floor_std == '高楼层' else 0.0,
        }

        log_debug(f"  发送 features: {json.dumps(features, ensure_ascii=False)}")

        # ---- 调用API（带重试） ----
        pred, err = call_api_with_retry(features, max_retries=2, timeout=3)
        if pred is not None:
            log_debug(f"  预测成功，结果 {pred}")
            predictions.append(pred)
        else:
            log_debug(f"  ❌ 预测失败: {err}")
            predictions.append(row['price'])  # 使用实际价格作为后备
            api_ok = False
            error_msg = err

    df_sample['predicted'] = predictions
    status = "✅ 所有数据预测成功" if api_ok else f"⚠️ 部分数据预测失败。{error_msg}"
    log_debug(f"最终状态: {status}")

    fig = px.bar(
        df_sample,
        x='title',
        y=['price', 'predicted'],
        title=f'{city} 实际价格 vs AI预测现在的房价（前10条记录）',
        labels={'value': '万元', 'title': '房源', 'variable': '类型'},
        barmode='group'
    )
    log_debug("========== 回调结束 ==========\n")
    return fig, status

# ---------- 启动 ----------
if __name__ == '__main__':
    app_dash.run(debug=True, port=8050)