import streamlit as st
import pandas as pd
import sqlite3
import json
import os
import numpy as np
import plotly.graph_objects as go
# 导入图片识别工具模块
from utils import extract_spectrum_master, pixels_to_real_data
#1.基础配置与全局变量
st.set_page_config(page_title="智能光谱检索系统", layout="wide", initial_sidebar_state="expanded")
DB_FILE = 'spectrum_db.sqlite'
if 'sample_df' not in st.session_state:
    st.session_state.sample_df = None
if 'sample_type' not in st.session_state:
    st.session_state.sample_type = None
if 'sample_name' not in st.session_state:
    st.session_state.sample_name = "Uploaded Sample"
#2.核心工具函数
def load_database_spectra(spectrum_type=None):
    """从数据库读取标准光谱，严格按类型筛选"""
    if not os.path.exists(DB_FILE):
        return []
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    spectra_data = []
    try:
        if spectrum_type:
            #按类型过滤
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
        #1.读取CSV（无表头模式）
        df_raw = pd.read_csv(uploaded_file, header=None, skip_blank_lines=True)
        
        # 检查第一行是"表头"还是"数据"
        first_row_str = df_raw.iloc[0].astype(str).tolist()
        first_row_lower = [s.lower() for s in first_row_str]
        
        # 判断第一行是否包含已知的表头关键词
        header_keywords = ['wavenumber', 'cm-1', 'cm^-1', '1/cm', '波数', 'kev', 'energy', 'channel', 'ch', '能量', 'm/z']
        first_row_is_header = any(any(kw in s for kw in header_keywords) for s in first_row_lower)
        
        if first_row_is_header:
            # 第一行是表头，按原逻辑处理
            headers = first_row_lower
            df = df_raw.drop(index=0).reset_index(drop=True)
        else:
            # 第一行是数据（无表头），不丢弃
            headers = None
            df = df_raw.reset_index(drop=True)
        
        x_col = None
        y_col = None
        s_type = "Unknown"
        
        #2.如果有表头，按表头关键词匹配
        if headers is not None:
            for i, h in enumerate(headers):
                # 【新增】优先检测 TIC 类型（m/z 是 TIC/质谱特有标识）
                if 'm/z' in h:
                    x_col, y_col, s_type = i, i+1, "TIC"
                    break
                if any(word in h for word in ['wavenumber', 'cm-1', 'cm^-1', '1/cm', '波数']):
                    if 'raman' in " ".join(headers):
                        x_col, y_col, s_type = i, i+1, "Raman"
                    else:
                        x_col, y_col, s_type = i, i+1, "FTIR"
                    break
                elif any(word in h for word in ['kev', 'energy', 'channel', 'ch', '能量']):
                    x_col, y_col, s_type = i, i+1, "XRF"
                    break
        
        #3.没有匹配到表头（或无表头），按数据值范围自动判断是XRD还是FTIR
        # 【注意】TIC数据若无表头，此处可能误判为FTIR/XRD，建议TIC文件保留表头（含m/z）
        if x_col is None and df.shape[1] >= 2:
            try:
                col0 = pd.to_numeric(df[0])
                col1 = pd.to_numeric(df[1])
                # FTIR波数范围4000~400 cm-1，最大值通常>1000
                # XRD的2θ范围通常5~90度，最大值通常<200
                if col0.max() > 1000:
                    x_col, y_col, s_type = 0, 1, "FTIR"
                else:
                    x_col, y_col, s_type = 0, 1, "XRD"
            except (ValueError, TypeError):
                pass
        
        #4.没有找到合适的列，返回错误
        if x_col is not None and y_col is not None:
            x_data = df[x_col].dropna().astype(float).tolist()
            y_data = df[y_col].dropna().astype(float).tolist()
            if len(x_data) > 0 and len(y_data) > 0:
                return x_data, y_data, s_type
        return None, None, None
    except Exception as e:
        print(f"解析文件出错: {e}")
        return None, None, None
def process_image_from_file(temp_path):
    """基于utils.py的提取函数，使用 OpenCV 图像处理 + 坐标校准
    参数：
        temp_path: 临时图片文件路径
    返回：
        (x_vals, y_vals, message)
        x_vals: 提取的X轴数据数组
        y_vals: 提取的Y轴数据数组
        message: 状态信息
    """
    #1.提取曲线像素坐标
    pixel_x, pixel_y, msg1 = extract_spectrum_master(temp_path)
    if pixel_x is None:
        return None, None, f"曲线提取失败: {msg1}"
    #2.换为真实光谱数据
    final_w, final_i, msg2 = pixels_to_real_data(pixel_x, pixel_y)
    if final_w is None:
        return None, None, f"数据转换失败: {msg2}"
    return final_w, final_i, f"{msg1}->{msg2}"
def calculate_similarity(df1, db_spec_dict):
    """终版匹配算法：使用近似连接(merge_asof)彻底无视浮点数微小误差"""
    try:
        #1.预处理数据，转为Pandas并强制清洗
        df1_clean = df1.copy()
        df2_clean = pd.DataFrame(db_spec_dict)
        df1_clean['wavenumbers'] = pd.to_numeric(df1_clean['wavenumbers'], errors='coerce')
        df2_clean['wavenumbers'] = pd.to_numeric(df2_clean['wavenumbers'], errors='coerce')
        df1_clean['intensities'] = pd.to_numeric(df1_clean['intensities'], errors='coerce')
        df2_clean['intensities'] = pd.to_numeric(df2_clean['intensities'], errors='coerce')
        #2.按波数排序
        df1_sorted = df1_clean.sort_values('wavenumbers')
        df2_sorted = df2_clean.sort_values('wavenumbers')
        #3.在±0.1的极小误差范围内进行模糊对齐
        merged = pd.merge_asof(
            df1_sorted, 
            df2_sorted, 
            on='wavenumbers', 
            direction='nearest',
            tolerance=0.1
        )
        #4.剔除空数据，提取对齐后的两组Y轴数据
        aligned = merged.dropna(subset=['intensities_y'])
        if len(aligned) < 50: return 0.0
        s1 = aligned['intensities_x'].values
        s2 = aligned['intensities_y'].values
        #5.全局归一化到0-1区间
        min_val = min(np.min(s1), np.min(s2))
        max_val = max(np.max(s1), np.max(s2))
        if max_val - min_val == 0: return 0.0
        s1_norm = (s1 - min_val) / (max_val - min_val)
        s2_norm = (s2 - min_val) / (max_val - min_val)
        #6.减去均值，计算余弦相似度
        s1_centered = s1_norm - np.mean(s1_norm)
        s2_centered = s2_norm - np.mean(s2_norm)
        norm_product = np.linalg.norm(s1_centered) * np.linalg.norm(s2_centered)
        if norm_product == 0: return 0.0
        cos_sim = np.dot(s1_centered, s2_centered) / norm_product
        percentage = max(0, (cos_sim + 1) / 2 * 100)
        return round(percentage, 2)
    except Exception as e:
        return 0.0
#3. Streamlit主界面逻辑
st.title("🔬 文物粘接材料谱图老化匹配系统")
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
                #XRD类型时显示Excel老化情况表下载链接
                if s_type == "XRD":
                    excel_path = 'XRD老化情况.xlsx'
                    if os.path.exists(excel_path):
                        with open(excel_path, 'rb') as f:
                            st.download_button(
                                label='📊 查看XRD老化情况表',
                                data=f,
                                file_name='XRD老化情况.xlsx',
                                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                            )
                    else:
                        st.warning('⚠️ XRD老化情况.xlsx 文件未找到，请确保文件与app.py在同一目录下')
                #FTIR类型时显示Excel文献下载链接
                if s_type == "FTIR":
                    excel_path = 'pdf期刊.xlsx'
                    if os.path.exists(excel_path):
                        with open(excel_path, 'rb') as f:
                            st.download_button(
                                label='📊 查看FTIR文献资料',
                                data=f,
                                file_name='pdf期刊.xlsx',
                                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                            )
                    else:
                        st.warning('⚠️ pdf期刊.xlsx 文件未找到，请确保文件与app.py在同一目录下')
            else:
                st.error("❌ 无法识别 CSV 表头。请确保包含波数/能量和强度列。")
    with tab2:
        st.markdown("### 📸 光谱图片识别模式")
        st.markdown("上传光谱曲线图片（如论文中的谱图截图、仪器导出图片等），系统将自动提取曲线数据并参与匹配检索。")
        img_file = st.file_uploader("上传光谱曲线图片 (jpg/png)", type=["jpg", "png", "jpeg"])
        if img_file is not None:
            st.image(img_file, use_column_width=True)
            if st.button("🚀 开始提取图片曲线"):
                temp_path = "temp_spectrum_upload.jpg"
                with open(temp_path, "wb") as f:
                    f.write(img_file.getbuffer())
                with st.spinner("🤖 正在提取曲线数据，请稍候..."):
                    x_vals, y_vals, msg = process_image_from_file(temp_path)
                    if x_vals is not None:
                        n_points = len(x_vals)
                        st.session_state.sample_df = pd.DataFrame({"wavenumbers": x_vals, "intensities": y_vals})
                        st.session_state.sample_type = "FTIR"  # 图片默认按FTIR处理
                        st.session_state.sample_name = f"图片提取({img_file.name})"
                        st.success(f"✅ {msg}（共 {n_points} 个点）")
                        st.info("💡 提示：图片数据已自动加载，右侧将自动进行匹配检索。如需校准坐标范围，请手动调整。")
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    else:
                        st.error(f"❌ {msg}")
                        st.warning("💡 建议：确保图片中曲线清晰、背景为白色、坐标轴可见")
with col2:
    st.header("📊 检索与匹配结果")
    # 【新增】数据库浏览功能 - 可查看TIC等所有类型数据
    with st.expander("🔍 浏览数据库内容"):
        db_type = st.selectbox("选择谱图类型", ["全部", "FTIR", "XRD", "XRF", "Raman", "TIC"])
        if db_type == "全部":
            db_spectra_browse = load_database_spectra(None)
        else:
            db_spectra_browse = load_database_spectra(db_type)
        if db_spectra_browse:
            browse_data = []
            for spec in db_spectra_browse:
                browse_data.append({
                    "谱图名称": spec['name'],
                    "来源论文": spec.get('source_tag', '未知'),
                    "数据点数": len(spec['wavenumbers']) if spec['wavenumbers'] else 0
                })
            if browse_data:
                st.dataframe(pd.DataFrame(browse_data), use_container_width=True, hide_index=True)
            else:
                st.info("数据库中暂无数据")
        else:
            st.info("数据库为空，请先运行 smart_import.py 导入数据")
    if st.session_state.sample_df is not None:
        #只加载和当前样品相同类型的数据库
        db_spectra = load_database_spectra(st.session_state.sample_type)
        if not db_spectra:
            st.warning(f"⚠️ 数据库中未找到 {st.session_state.sample_type} 标准数据，请先运行 `smart_import.py` 导入。")
        else:
            matches = []
            for spec in db_spectra:
                score = calculate_similarity(st.session_state.sample_df, spec)
                matches.append({'name': spec['name'], 'score': score, 'source_tag': spec.get('source_tag', ''), 'data': spec})
            #取前5
            matches.sort(key=lambda x: x['score'], reverse=True)
            top_5 = matches[:5]
            if not top_5 or top_5[0]['score'] < 50:
                 st.info("未在数据库中找到高匹配度的标准光谱 (Top1 < 50%)。")
            else:
                st.success(f"🏆 找到匹配度最高的 {len(top_5)} 条数据：")
                
                #XRD动态展示论文来源
                if st.session_state.sample_type == "XRD":
                    st.divider()
                    st.subheader("📄 关联论文来源")
                    for i, match in enumerate(top_5):
                        rank_emoji = ["🥇", "🥈", "🥉", "🏅", "🏅"][i]
                        paper_title = match.get('source_tag', '未找到来源')
                        st.markdown(f"{rank_emoji} **Top {i+1}** - 匹配度: `{match['score']:.2f}%`  \n📖 **来源论文**: *{paper_title}*")
                    st.divider()
                #2.展示数据表格
                df_top5 = pd.DataFrame(top_5)
                #根据类型设置显示中文表头
                if st.session_state.sample_type == "XRD":
                    display_names = {"name": "标准谱图文件名", "source_tag": "来源论文"}
                else:
                    display_names = {"name": "标准谱图名称", "source_tag": "来源"}
                #提取并显示指定列
                df_display = df_top5[['name', 'score', 'source_tag']].rename(columns={
                    'name': display_names['name'], 
                    'score': '匹配度 (%)',
                    'source_tag': display_names['source_tag']
                })
                #给第一行加背景色
                def highlight_top(row):
                    if row.name == 0:
                        return ['background-color: #d4edda', 'background-color: #d4edda', 'background-color: #d4edda']
                    return ['background-color: white', 'background-color: white', 'background-color: white']
                st.dataframe(
                    df_display.style.apply(highlight_top, axis=1).format({'匹配度 (%)': '{:.2f}'}),
                    use_container_width=True, hide_index=True
                )
                #2.使用Plotly交互式绘图
                fig = go.Figure()
                sample_name = st.session_state.sample_name
                #绘制上传样品
                fig.add_trace(go.Scatter(
                    x=st.session_state.sample_df['wavenumbers'],
                    y=st.session_state.sample_df['intensities'],
                    mode='lines', name=f"上传样品: {sample_name}",
                    line=dict(color='black', width=2)
                ))
                #绘制Top5
                colors = ['#FF0000', '#0000FF', '#008000', '#FFA500', '#800080']
                for i, match in enumerate(top_5):
                    fig.add_trace(go.Scatter(
                        x=match['data']['wavenumbers'],
                        y=match['data']['intensities'],
                        mode='lines', 
                        name=f"匹配 {i+1}: {match['name']} ({match['score']}%)",
                        line=dict(color=colors[i % 5], width=1.5)
                    ))
                #X轴反转
                fig.update_layout(
                    xaxis=dict(title="Wavenumbers / Energy"),
                    yaxis=dict(title="Intensity"),
                    xaxis_range=[None, None],#不反转X轴
                    title=f"光谱匹配曲线图",
                    legend_title="图例"
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("<br><br><p style='text-align:center; color:gray;'>👈 请在左侧上传 CSV 文件或图片开始检索</p>", unsafe_allow_html=True)