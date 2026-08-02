# dashboard/app.py
import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 配置文件
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import dash
from dash import dcc, html, Input, Output, State, dash_table
import plotly.express as px
import pandas as pd
import requests
from sqlalchemy import create_engine, text
import json
from datetime import datetime
import time

# ---------- 日志 ----------
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'log')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'dashboard_debug.log')


def log_debug(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(full_msg + '\n')


if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)
log_debug("========== Dashboard 启动 ==========")

# ---------- 配置 ----------
_API_HOST = os.environ.get('API_HOST', '127.0.0.1')
_API_PORT = os.environ.get('API_PORT', '8000')
API_BASE_URL = f'http://{_API_HOST}:{_API_PORT}'

# ---------- 连接数据库 ----------
_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'realestate.db')
engine = create_engine(f"sqlite:///{_DB_PATH}")


# ---------- 辅助函数：带重试的AI预测API调用 ----------
def call_api_with_retry(features, max_retries=2, timeout=3):
    """
    调用预测API，支持重试
    """
    url = f'{API_BASE_URL}/predict'
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, json=features, timeout=timeout)
            if resp.status_code == 200:
                return resp.json().get('predicted_price'), None
            else:
                return None, f"API返回 {resp.status_code}: {resp.text[:100]}"
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                log_debug(f"  请求超时，第 {attempt + 1} 次重试...")
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
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='city-store'),
    # ===== 主页面 =====
    html.Div(id='main-page', children=[
        html.H1("🏠 全国二手房数据看板（AI预测版）", style={'textAlign': 'center'}),
        dcc.Dropdown(
            id='city-filter',
            options=[{'label': c, 'value': c} for c in ['北京', '上海', '广州', '深圳']],
            value='北京'
        ),
        # 第一行：两个并排图表（散点图 + 历史趋势）
        html.Div([
            dcc.Graph(id='price-scatter', style={'width': '49%', 'display': 'inline-block'}),
            dcc.Graph(id='history-trend', style={'width': '49%', 'display': 'inline-block'})
        ]),
        # 第二行：两个并排图表（预测对比 + 未来预测）
        html.Div([
            dcc.Graph(id='prediction-vs-actual', style={'width': '49%', 'display': 'inline-block'}),
            dcc.Graph(id='future-prediction', style={'width': '49%', 'display': 'inline-block'})
        ]),
        html.Div(id='status-message', style={'textAlign': 'center', 'color': 'gray'}),
        html.Div(id='status-future', style={'textAlign': 'center', 'color': 'gray'}),
        # 🆕 查看更多按钮
        html.Div(
            html.Button('📋 查看更多', id='btn-more', n_clicks=0,
                        style={'fontSize': '16px', 'padding': '10px 24px', 'cursor': 'pointer',
                               'marginTop': '10px'}),
            style={'textAlign': 'center'}
        ),
    ]),
    # ===== 详情页 =====
    html.Div(id='detail-page', style={'display': 'none'}, children=[
        html.Div([
            html.Button('← 返回看板', id='btn-back', n_clicks=0,
                        style={'fontSize': '16px', 'padding': '8px 20px', 'cursor': 'pointer'}),
            html.H2(id='detail-title', style={'display': 'inline-block', 'marginLeft': '20px'}),
        ], style={'padding': '16px'}),
        # 筛选器
        html.Div([
            html.Label('户型：'),
            dcc.Dropdown(id='detail-layout-filter',
                         options=[{'label': '全部', 'value': 'all'}],
                         value='all', style={'width': '200px', 'display': 'inline-block'}),
            html.Label('楼层：', style={'marginLeft': '20px'}),
            dcc.Dropdown(id='detail-floor-filter',
                         options=[{'label': '全部', 'value': 'all'}],
                         value='all', style={'width': '200px', 'display': 'inline-block'}),
            html.Label('排序：', style={'marginLeft': '20px'}),
            dcc.Dropdown(id='detail-sort',
                         options=[
                             {'label': '默认', 'value': 'default'},
                             {'label': '总价从低到高', 'value': 'price_asc'},
                             {'label': '总价从高到低', 'value': 'price_desc'},
                             {'label': '面积从小到大', 'value': 'area_asc'},
                             {'label': '面积从大到小', 'value': 'area_desc'},
                         ],
                         value='default', style={'width': '200px', 'display': 'inline-block'}),
        ], style={'padding': '0 16px 16px'}),
        # 数据表
        html.Div(id='detail-table-container', style={'padding': '0 16px'}),
    ]),
])


# ---------- 回调1：散点图（保持不变） ----------
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


# 🆕 新增：回调2 - 历史走势图（按年份展示均价）
@app_dash.callback(
    Output('history-trend', 'figure'),
    Input('city-filter', 'value')
)
def update_history(city):
    log_debug(f"历史趋势回调触发，城市={city}")
    df = pd.read_sql(text("SELECT year, price FROM houses WHERE city=:city"), engine, params={"city": city})
    if df.empty:
        log_debug(f"城市 {city} 无历史数据")
        return px.line(title=f'{city} 暂无历史数据')
    # 按年份计算均价
    avg_df = df.groupby('year')['price'].mean().reset_index()
    fig = px.line(avg_df, x='year', y='price',
                  title=f'{city} 历史均价走势',
                  labels={'year': '年份', 'price': '均价(万元)'},
                  markers=True)
    return fig


# 🔄 修改：回调3 - 预测对比图（增加 year 字段）
@app_dash.callback(
    Output('prediction-vs-actual', 'figure'),
    Output('status-message', 'children'),
    Output('city-store', 'data'),
    Input('city-filter', 'value')
)
def update_prediction(city):
    log_debug(f"========== 预测回调触发，城市={city} ==========")

    df = pd.read_sql("SELECT * FROM houses", engine)
    df_city = df[df['city'] == city]
    if df_city.empty:
        log_debug(f"城市 {city} 无数据")
        return px.bar(title=f'{city} 暂无数据'), f'⚠️ 城市 {city} 无数据', ''

    layouts = df_city['layout'].dropna().unique()
    floors = df_city['floor_info'].dropna().unique()
    log_debug(f"数据库中的户型值: {layouts}")
    log_debug(f"数据库中的楼层值: {floors}")

    df_sample = df_city.sample(min(10, len(df_city))).copy()
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
        current_year = datetime.now().year
        if pd.isnull(year_val) or not (1900 <= year_val < current_year):
            year_val = 2000
            log_debug(f"  建成年份无效，设为2000")

        # 🔄 新增：提取交易年份（用于预测）
        trade_year = int(row['year']) if 'year' in row and pd.notnull(row['year']) else 2020
        log_debug(f"  交易年份: {trade_year}")

        # ---- 清洗分类 ----
        layout_raw = str(row.get('layout', '')).strip()
        floor_raw = str(row.get('floor_info', '')).strip()
        layout_std = layout_map.get(layout_raw, '3室2厅')
        floor_std = floor_map.get(floor_raw, '中楼层')
        log_debug(f"  layout: '{layout_raw}' -> '{layout_std}', floor: '{floor_raw}' -> '{floor_std}'")

        # ---- 构造特征（修复版：增加 year 和 city） ----
        features = {
            'year': trade_year,  # 🔥 必须传年份
            'area': float(area_val),
            'building_year': int(year_val),
            # 🔥 必须传城市（根据当前选中的 city 决定）
            'city_北京': 1.0 if city == '北京' else 0.0,
            'city_上海': 1.0 if city == '上海' else 0.0,
            'city_广州': 1.0 if city == '广州' else 0.0,
            'city_深圳': 1.0 if city == '深圳' else 0.0,
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
            predictions.append(row['price'])
            api_ok = False
            error_msg += '\n' + err

    df_sample['predicted'] = predictions
    status = "✅ 所有房源数据预测成功" if api_ok else f"⚠️ 部分房源数据预测失败。{error_msg}"
    log_debug(f"最终状态: {status}")

    fig = px.bar(
        df_sample,
        x='title',
        y=['price', 'predicted'],
        title=f'{city} 实际价格 vs AI预测价格（随机10条记录）',
        labels={'value': '万元', 'title': '房源', 'variable': '类型'},
        barmode='group'
    )
    log_debug("========== 回调结束 ==========\n")
    return fig, status, city


# 🆕 新增：回调4 - 未来3年预测曲线
@app_dash.callback(
    Output('future-prediction', 'figure'),
    Output('status-future', 'children'),
    Input('city-filter', 'value')
)
def update_future(city):
    log_debug(f"========== 未来预测回调触发，城市={city} ==========")

    # 取该城市最新一条记录作为参考样本
    df = pd.read_sql(text("SELECT * FROM houses WHERE city=:city ORDER BY year DESC LIMIT 1"), engine, params={"city": city})
    if df.empty:
        log_debug(f"城市 {city} 无样本")
        return px.scatter(title=f'{city} 无样本，无法预测未来'), f'⚠️ 城市 {city} 无样本'

    sample = df.iloc[0]
    current_year = datetime.now().year
    future_years = [current_year + i for i in range(1, 4)]  # 未来3年(+1,2,3)

    # ---- 清洗数值 ----
    area_val = sample['area']
    if pd.isnull(area_val) or area_val <= 0:
        area_val = 80.0
        log_debug(f"  面积无效，设为80")

    year_val = sample['building_year']
    if pd.isnull(year_val) or not (1900 <= year_val < current_year):
        year_val = 2000
        log_debug(f"  建成年份无效，设为2000")

    # ---- 清洗分类（映射归一化） ----
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
    layout_raw = str(sample.get('layout', '')).strip()
    floor_raw = str(sample.get('floor_info', '')).strip()
    layout_std = layout_map.get(layout_raw, '3室2厅')
    floor_std = floor_map.get(floor_raw, '中楼层')

    log_debug(f"参考样本年份: {sample['year']}, 面积: {area_val}, 户型: '{layout_raw}' -> '{layout_std}', 楼层: '{floor_raw}' -> '{floor_std}'")

    predictions = []
    pred_years = []
    api_ok = True
    error_msg = ""

    for yr in future_years:
        # 构造特征（使用归一化后的样本特征，只改变年份）
        features = {
            'year': yr,  # 核心：传入未来年份
            'area': float(area_val),
            'building_year': int(year_val),
            'city_北京': 1 if city == '北京' else 0,
            'city_上海': 1 if city == '上海' else 0,
            'city_广州': 1 if city == '广州' else 0,
            'city_深圳': 1 if city == '深圳' else 0,
            'layout_2室1厅': 1 if layout_std == '2室1厅' else 0,
            'layout_3室1厅': 1 if layout_std == '3室1厅' else 0,
            'layout_3室2厅': 1 if layout_std == '3室2厅' else 0,
            'floor_info_低楼层': 1 if floor_std == '低楼层' else 0,
            'floor_info_中楼层': 1 if floor_std == '中楼层' else 0,
            'floor_info_高楼层': 1 if floor_std == '高楼层' else 0,
        }

        log_debug(f"预测 {yr} 年，特征: {json.dumps(features, ensure_ascii=False)}")
        pred, err = call_api_with_retry(features, max_retries=2, timeout=3)
        if pred is not None:
            predictions.append(pred)
            pred_years.append(yr)
            log_debug(f"  {yr}年预测成功: {pred}")
        else:
            log_debug(f"  {yr}年预测失败: {err}")
            api_ok = False
            error_msg += '\n' + err

    if not predictions:
        return px.scatter(title='未来预测失败（API未响应）'), f'❌ 未来预测失败（API未响应）'

    df_future = pd.DataFrame({'year': pred_years, 'pred_price': predictions})
    fig = px.line(df_future, x='year', y='pred_price', markers=True,
                  title=f'{city} 未来3年价格预测（基于 {sample["year"]} 年样本）',
                  labels={'year': '年份', 'pred_price': '预测总价(万元)'})
    status = "✅ 未来3年预测成功" if api_ok else f"⚠️ 部分年份预测失败。{error_msg}"
    log_debug(f"========== 未来预测回调结束，状态: {status} ==========\n")
    return fig, status


# 🆕 回调5：页面导航 - 查看更多
@app_dash.callback(
    Output('url', 'pathname', allow_duplicate=True),
    Input('btn-more', 'n_clicks'),
    prevent_initial_call=True
)
def navigate_to_detail(n_clicks):
    if n_clicks:
        return '/details'
    return dash.no_update


# 🆕 回调6：页面导航 - 返回
@app_dash.callback(
    Output('url', 'pathname', allow_duplicate=True),
    Input('btn-back', 'n_clicks'),
    prevent_initial_call=True
)
def navigate_back(n_clicks):
    if n_clicks:
        return '/'
    return dash.no_update


# 🆕 回调7：主页面 / 详情页 显示切换
@app_dash.callback(
    Output('main-page', 'style'),
    Output('detail-page', 'style'),
    Input('url', 'pathname')
)
def show_page(pathname):
    if pathname == '/details':
        return {'display': 'none'}, {}
    return {}, {'display': 'none'}


# 🆕 回调8：详情页 - 筛选器选项 + 数据表
@app_dash.callback(
    Output('detail-table-container', 'children'),
    Output('detail-layout-filter', 'options'),
    Output('detail-floor-filter', 'options'),
    Output('detail-title', 'children'),
    Input('city-store', 'data'),
    Input('detail-layout-filter', 'value'),
    Input('detail-floor-filter', 'value'),
    Input('detail-sort', 'value'),
    prevent_initial_call=True
)
def update_detail_table(city, layout_val, floor_val, sort_val):
    if not city:
        return html.P('请先在看板中选择城市'), [], [], ''

    df = pd.read_sql("SELECT * FROM houses", engine)
    df_city = df[df['city'] == city].copy()

    if df_city.empty:
        return html.P(f'{city} 暂无数据'), [], [], f'{city} 全部房源数据'

    # ---- 生成筛选器选项 ----
    layouts = sorted(df_city['layout'].dropna().unique().tolist())
    floors = sorted(df_city['floor_info'].dropna().unique().tolist())
    layout_opts = [{'label': '全部', 'value': 'all'}] + [{'label': l, 'value': l} for l in layouts]
    floor_opts = [{'label': '全部', 'value': 'all'}] + [{'label': f, 'value': f} for f in floors]

    # ---- 筛选 ----
    if layout_val and layout_val != 'all':
        df_city = df_city[df_city['layout'] == layout_val]
    if floor_val and floor_val != 'all':
        df_city = df_city[df_city['floor_info'] == floor_val]

    # ---- 排序 ----
    if sort_val == 'price_asc':
        df_city = df_city.sort_values('price', ascending=True)
    elif sort_val == 'price_desc':
        df_city = df_city.sort_values('price', ascending=False)
    elif sort_val == 'area_asc':
        df_city = df_city.sort_values('area', ascending=True)
    elif sort_val == 'area_desc':
        df_city = df_city.sort_values('area', ascending=False)

    # ---- 构造表格 ----
    col_map = {
        'title': '标题', 'price': '总价(万)', 'area': '面积(㎡)',
        'layout': '户型', 'floor_info': '楼层', 'building_year': '建成年份',
        'year': '交易年份',
    }
    display_cols = list(col_map.keys())
    display_names = [col_map[c] for c in display_cols]

    table_df = df_city[display_cols].copy()
    table_df.columns = display_names

    table = dash_table.DataTable(
        data=table_df.to_dict('records'),
        columns=[{'name': c, 'id': c} for c in display_names],
        page_size=20,
        sort_action='native',
        filter_action='native',
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'center', 'padding': '8px'},
        style_header={'backgroundColor': '#f0f0f0', 'fontWeight': 'bold'},
        style_data_conditional=[{
            'if': {'row_index': 'odd'},
            'backgroundColor': '#fafafa'
        }],
    )

    title = f'{city} 全部房源数据（共 {len(df_city)} 条）'
    return table, layout_opts, floor_opts, title



# ---------- 启动 ----------
if __name__ == '__main__':
    d_host = os.environ.get('DASHBOARD_HOST', '127.0.0.1')
    d_port = int(os.environ.get('DASHBOARD_PORT', '8050'))
    app_dash.run(debug=True, host=d_host, port=d_port)