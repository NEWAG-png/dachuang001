import streamlit as st
import pandas as pd
import sqlite3
import json
import os
import numpy as np
import plotly.graph_objects as go
import cv2
import re
from io import BytesIO

# --- 1. 基础配置与全局变量 ---
st.set_page_config(page_title="智能光谱检索系统", layout="wide", initial_sidebar_state="expanded")
DB_FILE = 'spectrum_data.db'

if 'sample_df' not in st.session_state:
    st.session_state.sample_df = None
if 'sample_type' not in st.session_state:
    st.session_state.sample_type = None
if 'sample_name' not in st.session_state:
    st.session_state.sample_name = "Uploaded Sample"

# --- 2. 核心工具函数 ---

def load_database_spectra(spectrum_type=None):
    """从数据库读取标准光谱，严格按类型筛选"""
    if not os.path.exists(DB_FILE):
        return []
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    spectra_data = []
    
    try:
        if spectrum_type:
            # 核心修复：按类型过滤，FTIR 和 XRF 绝不混比
            query = "SELECT spectrum_name, source_tag, wavenumbers, intensities FROM spectra WHERE spectrum_type = ?"
            cursor.execute(query, (spectrum_type,))
        else:
            query = "SELECT spectrum_name, source_tag, wavenumbers, intensities FROM spectra"
            cursor.execute(query)
            
        rows = cursor.fetchall()
        for row in rows:
            name, source_tag, wavenums_str, ints_str = row
            spectra_data.append({
                'name': name,
                'source_tag': source_tag if source_tag else '',
                'wavenumbers': json.loads(wavenums_str),
                'intensities': json.loads(ints_str)
            })
    except Exception as e:
        st.error(f"数据库读取失败: {e}")
    finally:
        conn.close()
    return spectra_data

def parse_csv(uploaded_file):
    try:
        # 1. 尝试读取表头
        df = pd.read_csv(uploaded_file, header=None, skip_blank_lines=True)
        headers = df.iloc[0].astype(str).str.lower().tolist()
        df = df.drop(index=0).reset_index(drop=True)
        
        x_col = None
        y_col = None
        s_type = "Unknown"
        
        # 2. 按表头关键词匹配 FTIR, Raman, XRF
        for i, h in enumerate(headers):
            # FTIR / Raman 锁定
            if any(word in h for word in ['wavenumber', 'cm-1', 'cm^-1', '1/cm', '波数']):
                if 'raman' in " ".join(headers):
                    x_col, y_col, s_type = i, i+1, "Raman"
                else:
                    x_col, y_col, s_type = i, i+1, "FTIR"
                break
            # XRF 锁定
            elif any(word in h for word in ['kev', 'energy', 'channel', 'ch', '能量']):
                x_col, y_col, s_type = i, i+1, "XRF"
                break
                
        # 3. 如果没有匹配到表头（无表头文件），按位置强制抓取前两列作为 XRD
        if x_col is None and df.shape[1] >= 2:
            try:
                # 检查前两列是不是都是纯数字
                pd.to_numeric(df[0])
                pd.to_numeric(df[1])
                x_col, y_col, s_type = 0, 1, "XRD"
            except ValueError:
                pass
        
        if x_col is not None and y_col is not None:
            x_data = df[x_col].dropna().astype(float).tolist()
            y_data = df[y_col].dropna().astype(float).tolist()
            
            if len(x_data) > 0 and len(y_data) > 0:
                return x_data, y_data, s_type
            
        return None, None, None
        
    except Exception as e:
        print(f"解析文件出错: {e}")
        return None, None, None

def process_image(uploaded_file):
    """使用 OpenCV 从光谱图片中提取曲线数据"""
    img_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
    if img is None: return None, None
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) == 0: return None, None
    
    # 提取曲线 Y 坐标并映射到 X 轴（简化版提取，实际应用需先校准坐标轴）
    h, w, _ = img.shape
    y_vals = coords[:, 0]
    x_vals = coords[:, 1]
    
    # 简单的模拟映射，实际使用需手动设置图像坐标范围
    return x_vals, -y_vals + h 

def calculate_similarity(df1, db_spec_dict):
    """终极匹配算法：使用近似连接(merge_asof)彻底无视浮点数微小误差"""
    try:
        # 1. 预处理数据，转为 Pandas DataFrame 并强制清洗类型
        df1_clean = df1.copy()
        df2_clean = pd.DataFrame(db_spec_dict)
        
        df1_clean['wavenumbers'] = pd.to_numeric(df1_clean['wavenumbers'], errors='coerce')
        df2_clean['wavenumbers'] = pd.to_numeric(df2_clean['wavenumbers'], errors='coerce')
        
        df1_clean['intensities'] = pd.to_numeric(df1_clean['intensities'], errors='coerce')
        df2_clean['intensities'] = pd.to_numeric(df2_clean['intensities'], errors='coerce')
        
        # 2. 按波数排序（使用 merge_asof 必须先排序）
        df1_sorted = df1_clean.sort_values('wavenumbers')
        df2_sorted = df2_clean.sort_values('wavenumbers')

        # 3. 核心黑科技：在 ±0.1 的极小误差范围内进行模糊对齐
        # 只要两个波数相差不到 0.1，就直接视为同一个点！
        merged = pd.merge_asof(
            df1_sorted, 
            df2_sorted, 
            on='wavenumbers', 
            direction='nearest',
            tolerance=0.1
        )
        
        # 4. 剔除没能对齐的空数据，并提取对齐后的两组 Y 轴数据
        aligned = merged.dropna(subset=['intensities_y'])
        if len(aligned) < 50: return 0.0
        
        s1 = aligned['intensities_x'].values
        s2 = aligned['intensities_y'].values

        # 5. 全局归一化到 0-1 区间
        min_val = min(np.min(s1), np.min(s2))
        max_val = max(np.max(s1), np.max(s2))
        if max_val - min_val == 0: return 0.0
        
        s1_norm = (s1 - min_val) / (max_val - min_val)
        s2_norm = (s2 - min_val) / (max_val - min_val)
        
        # 6. 减去均值，计算余弦相似度
        s1_centered = s1_norm - np.mean(s1_norm)
        s2_centered = s2_norm - np.mean(s2_norm)
        
        norm_product = np.linalg.norm(s1_centered) * np.linalg.norm(s2_centered)
        if norm_product == 0: return 0.0
        
        cos_sim = np.dot(s1_centered, s2_centered) / norm_product
        percentage = max(0, (cos_sim + 1) / 2 * 100)
        return round(percentage, 2)
        
    except Exception as e:
        return 0.0

# --- 3. Streamlit 主界面逻辑 ---

st.title("🔬 红外 / XRF 光谱智能检索系统")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("📤 上传样品")
    
    tab1, tab2 = st.tabs(["上传 CSV", "上传光谱图片"])
    
    with tab1:
        uploaded_file = st.file_uploader("请上传 CSV 文件", type=["csv"])
        if uploaded_file is not None:
            x_sample, y_sample, s_type = parse_csv(uploaded_file)
            if x_sample is not None:
                st.session_state.sample_df = pd.DataFrame({"wavenumbers": x_sample, "intensities": y_sample})
                st.session_state.sample_type = s_type
                st.session_state.sample_name = uploaded_file.name
                st.success(f"✅ 解析成功 ({len(x_sample)} 个点)")
                st.info(f"🔍 系统自动识别：您上传的是 **{s_type}** 光谱数据")
            else:
                st.error("❌ 无法识别 CSV 表头。请确保包含波数/能量和强度列。")

    with tab2:
        img_file = st.file_uploader("上传光谱曲线图片 (jpg/png)", type=["jpg", "png", "jpeg"])
        if img_file is not None:
            st.image(img_file, use_column_width=True)
            if st.button("🚀 开始提取图片曲线"):
                x_vals, y_vals = process_image(img_file)
                if x_vals is not None:
                    # 提取的图片数据通常 X 轴是像素，这里仅作测试用
                    st.session_state.sample_df = pd.DataFrame({"wavenumbers": x_vals, "intensities": y_vals})
                    st.session_state.sample_type = "FTIR"  # 图片默认按FTIR处理
                    st.session_state.sample_name = "Extracted from Image"
                    st.success("✅ 图片曲线提取成功！")
                else:
                    st.error("提取失败，请确保背景为白色、曲线为深色。")

with col2:
    st.header("📊 检索与匹配结果")
    
    if st.session_state.sample_df is not None:
        # 核心修复：只加载和当前样品相同类型的数据库
        db_spectra = load_database_spectra(st.session_state.sample_type)
        
        if not db_spectra:
            st.warning(f"⚠️ 数据库中未找到 {st.session_state.sample_type} 标准数据，请先运行 `smart_import.py` 导入。")
        else:
            matches = []
            for spec in db_spectra:
                score = calculate_similarity(st.session_state.sample_df, spec)
                matches.append({'name': spec['name'], 'score': score, 'source_tag': spec.get('source_tag', ''), 'data': spec})
            
            # 按相似度降序排列，取前 5
            matches.sort(key=lambda x: x['score'], reverse=True)
            top_5 = matches[:5]
            
            if not top_5 or top_5[0]['score'] < 50:
                 st.info("未在数据库中找到高匹配度的标准光谱 (Top1 < 50%)。")
            else:
                st.success(f"🏆 找到匹配度最高的 {len(top_5)} 条数据：")
                
                # === XRD 专属：动态展示论文来源 ===
                if s_type == "XRD":
                    st.divider()
                    st.subheader("📄 关联论文来源")
                    for i, match in enumerate(top_5):
                        rank_emoji = ["🥇", "🥈", "🥉", "🏅", "🏅"][i]
                        paper_title = match.get('source_tag', '未找到来源')
                        st.markdown(f"{rank_emoji} **Top {i+1}** - 匹配度: `{match['score']:.2f}%`  \n📖 **来源论文**: *{paper_title}*")
                    st.divider()
                
                # 2. 展示数据表格（含 source_tag）
                df_top5 = pd.DataFrame(top_5)
                
                # 根据类型设置显示中文表头
                if s_type == "XRD":
                    display_names = {"name": "标准谱图文件名", "source_tag": "来源论文"}
                else:
                    display_names = {"name": "标准谱图名称", "source_tag": "来源"}
                
                # 提取并显示指定列
                df_display = df_top5[['name', 'score', 'source_tag']].rename(columns={
                    'name': display_names['name'], 
                    'score': '匹配度 (%)',
                    'source_tag': display_names['source_tag']
                })
                
                # 自定义高亮函数：只给第一行（最高分）加背景色
                def highlight_top(row):
                    if row.name == 0:
                        return ['background-color: #d4edda', 'background-color: #d4edda', 'background-color: #d4edda']
                    return ['background-color: white', 'background-color: white', 'background-color: white']

                st.dataframe(
                    df_display.style.apply(highlight_top, axis=1).format({'匹配度 (%)': '{:.2f}'}),
                    use_container_width=True, hide_index=True
                )

                # 2. 使用 Plotly 交互式绘图
                fig = go.Figure()
                sample_name = st.session_state.sample_name
                
                # 绘制上传样品
                fig.add_trace(go.Scatter(
                    x=st.session_state.sample_df['wavenumbers'],
                    y=st.session_state.sample_df['intensities'],
                    mode='lines', name=f"上传样品: {sample_name}",
                    line=dict(color='black', width=2)
                ))
                
                # 绘制 Top5 标准库
                colors = ['#FF0000', '#0000FF', '#008000', '#FFA500', '#800080']
                for i, match in enumerate(top_5):
                    fig.add_trace(go.Scatter(
                        x=match['data']['wavenumbers'],
                        y=match['data']['intensities'],
                        mode='lines', 
                        name=f"匹配 {i+1}: {match['name']} ({match['score']}%)",
                        line=dict(color=colors[i % 5], width=1.5)
                    ))
                
                # 设置X轴反转（光谱惯例）
                fig.update_layout(
                    xaxis=dict(title="Wavenumbers / Energy", autorange='reversed'),
                    yaxis=dict(title="Intensity"),
                    title=f"光谱匹配曲线图",
                    legend_title="图例"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
    else:
        st.markdown("<br><br><p style='text-align:center; color:gray;'>👈 请在左侧上传 CSV 文件或图片开始检索</p>", unsafe_allow_html=True)