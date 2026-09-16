import streamlit as st
import pandas as pd
import sqlite3
import json
import numpy as np
import os
import ast
from scipy.interpolate import interp1d

# 【关键】导入你刚刚升级的 utils.py 中的函数
try:
    from utils import clean_and_parse_data, extract_spectrum_master, pixels_to_real_data
except ImportError as e:
    st.error(f"❌ 导入 utils.py 失败，请确保 utils.py 在同目录下且包含必要函数。错误: {e}")
    st.stop()

st.set_page_config(page_title="FTIR 红外光谱智能检索系统", layout="wide")
st.title("🔬 FTIR 红外光谱智能检索系统 (Top 5 匹配版)")

# --- 1. 侧边栏：选择上传方式 ---
with st.sidebar:
    st.header("📂 上传样品数据")
    
    # 新增：让用户选择是传文件还是传图片
    upload_mode = st.radio("数据来源", ("上传 CSV 文件", "上传光谱图片"))
    
    uploaded_file = None
    if upload_mode == "上传 CSV 文件":
        uploaded_file = st.file_uploader("请上传 CSV 文件", type=["csv"])
    else:
        uploaded_file = st.file_uploader("请上传光谱图片", type=["jpg", "png", "jpeg"])
    
    if uploaded_file is not None:
        st.success(f"已加载: {uploaded_file.name}")

# --- 2. 核心工具函数 (完全保留你原有的逻辑) ---

def parse_json_safe(json_str):
    """万能解析器"""
    if not json_str or not isinstance(json_str, str): return None
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        try: data = ast.literal_eval(json_str)
        except (ValueError, SyntaxError): return None
    if isinstance(data, dict) and 'wavenumbers' in data and 'intensities' in data:
        return data
    return None

# ================== 🔥 核心修改点 1：加过滤条件 ==================
def load_database_spectra(source_tag='Standard'):
    """从数据库加载光谱，默认只加载标准库，防止自己跟自己比"""
    db_path = 'spectrum_data.db'
    if not os.path.exists(db_path):
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # 【关键修改】加上 WHERE 条件，只查 source_tag 匹配的数据
        cursor.execute(
            "SELECT id, material_name, spectrum_type, data_json FROM spectra WHERE source_tag = ?", 
            (source_tag,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        valid_spectra = []
        for row in rows:
            spec_id, material_name, spectrum_type, data_json_str = row
            parsed_data = parse_json_safe(data_json_str)
            if parsed_data:
                try:
                    wavenumbers = np.array(parsed_data['wavenumbers'], dtype=float)
                    intensities = np.array(parsed_data['intensities'], dtype=float)
                    valid_spectra.append({
                        'id': spec_id, 'name': material_name, 'type': spectrum_type,
                        'wavenumbers': wavenumbers, 'intensities': intensities
                    })
                except (ValueError, TypeError): continue
        return valid_spectra
    except Exception as e:
        st.error(f"❌ 读取数据库失败: {str(e)}")
        return []
# =================================================================

def interpolate_spectrum(wavenumbers, intensities, target_wavenumbers):
    """插值对齐"""
    sort_idx = np.argsort(wavenumbers)
    wavenumbers = wavenumbers[sort_idx]
    intensities = intensities[sort_idx]
    interp_func = interp1d(wavenumbers, intensities, kind='linear', bounds_error=False, fill_value=0.0)
    return interp_func(target_wavenumbers)

def calculate_similarity(spec1_intensities, spec2_intensities):
    """计算余弦相似度"""
    norm1 = np.linalg.norm(spec1_intensities)
    norm2 = np.linalg.norm(spec2_intensities)
    if norm1 == 0 or norm2 == 0: return 0.0
    normalized_spec1 = spec1_intensities / norm1
    normalized_spec2 = spec2_intensities / norm2
    cosine_sim = np.dot(normalized_spec1, normalized_spec2)
    return cosine_sim

def save_to_db(file_name, material_name, spectrum_type, wavenumbers, intensities, source_tag='User_Upload'):
    """通用入库函数 (已适配你的 init_db.py 字段名)"""
    try:
        data_dict = {'wavenumbers': wavenumbers.tolist(), 'intensities': intensities.tolist()}
        data_json = json.dumps(data_dict)
        
        conn = sqlite3.connect('spectrum_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO spectra (file_name, material_name, spectrum_type, data_json, source_tag)
            VALUES (?, ?, ?, ?, ?)
        ''', (file_name, material_name, spectrum_type, data_json, source_tag))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"❌ 存入数据库失败: {str(e)}")
        return False

# --- 3. 主程序逻辑 ---

# ================== 🔥 核心修改点 2：明确加载标准库 ==================
# 这里显式传入 'Standard'，确保待测样品入库后，不会干扰当前的匹配结果
db_spectra = load_database_spectra(source_tag='Standard') 
# =================================================================

if db_spectra:
    st.success(f"✅ 成功加载 {len(db_spectra)} 条标准库光谱")
else:
    st.warning("⚠️ 数据库为空或无法读取有效数据。")

sample_wavenumbers, sample_intensities = None, None

# === 分支 A：处理 CSV 上传 (原有逻辑) ===
if upload_mode == "上传 CSV 文件" and uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        if len(df.columns) >= 2:
            sample_wavenumbers = df.iloc[:, 0].values.astype(float)
            sample_intensities = df.iloc[:, 1].values.astype(float)
            st.success(f"✅ CSV 解析成功！点数: {len(sample_wavenumbers)}")
        else:
            st.error("❌ CSV 文件至少需要两列数据")
    except Exception as e:
        st.error(f"❌ CSV 解析失败: {str(e)}")

# === 分支 B：处理图片上传 (新增逻辑) ===
elif upload_mode == "上传光谱图片" and uploaded_file is not None:
    st.header("📸 图片识别模式")
    st.image(uploaded_file, caption="用户上传的原图", use_column_width=True)
    
    # 保存临时文件供 OpenCV 读取
    temp_path = "temp_spectrum.jpg"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    with st.spinner("🤖 AI 正在提取曲线并清洗数据，请稍候..."):
        # 1. 提取像素坐标
        pixel_x, pixel_y, msg = extract_spectrum_master(temp_path)
        
        if pixel_x is not None:
            # 2. 将像素坐标转换为真实物理量，并自动对齐到 1000 个点
            final_w, final_i, msg2 = pixels_to_real_data(pixel_x, pixel_y)
            
            if final_w is not None:
                st.success(f"{msg} -> {msg2}")
                sample_wavenumbers, sample_intensities = final_w, final_i
                
                # 3. 自动存入数据库 (标签为 User_Upload，作为历史记录保留，但不参与本次比对)
                save_to_db(uploaded_file.name, "待测样品(图片)", "吸光度", final_w, final_i, source_tag='User_Upload')
                st.info("✅ 图片数据已自动存入历史记录，并参与后续匹配计算！")
            else:
                st.error(f"❌ 像素转真实数据失败: {msg2}")
        else:
            st.error(f"❌ 曲线识别失败: {msg}")

# === 分支 C：计算相似度并展示结果 (智能防翻车版) ===
if sample_wavenumbers is not None and db_spectra:
    all_wavenumbers = [sample_wavenumbers] + [spec['wavenumbers'] for spec in db_spectra]
    min_wn = max(np.min(wn) for wn in all_wavenumbers)
    max_wn = min(np.max(wn) for wn in all_wavenumbers)
    
    if min_wn < max_wn:
        target_wavenumbers = np.arange(min_wn, max_wn, 1.0)
        sample_interpolated = interpolate_spectrum(sample_wavenumbers, sample_intensities, target_wavenumbers)
        
        # 🔥 【核心新增】：智能方向判断（防透过率翻车）
        # 拿库里第一条数据做个“探针”，看看是正向相似度高，还是反向相似度高
        test_spec = db_spectra[0]
        test_db_interp = interpolate_spectrum(test_spec['wavenumbers'], test_spec['intensities'], target_wavenumbers)
        
        sim_normal = calculate_similarity(sample_interpolated, test_db_interp)
        sim_inverted = calculate_similarity(-sample_interpolated, test_db_interp) # 取反测试
        
        # 如果反向相似度更高，说明用户上传的是透过率谱，系统自动将其翻转为吸光度
        final_sample_data = sample_interpolated
        if sim_inverted > sim_normal:
            final_sample_data = -sample_interpolated 
            st.warning("⚠️ **系统自动纠错**：检测到您上传的是【透过率】谱图，已自动将其翻转为吸光度模式进行匹配！")
        # 🔥 【核心新增结束】

        # 接下来用处理后的 final_sample_data 进行正式比对
        similarities = []
        for spec in db_spectra:
            db_interpolated = interpolate_spectrum(spec['wavenumbers'], spec['intensities'], target_wavenumbers)
            # 注意：这里用的是 final_sample_data
            sim = calculate_similarity(final_sample_data, db_interpolated)
            similarities.append({'name': spec['name'], 'type': spec['type'], 'similarity': sim})
        
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        top5 = similarities[:5]
        
        st.subheader("🏆 Top 5 匹配结果")
        for i, result in enumerate(top5, 1):
            st.metric(label=f"第 {i} 名: {result['name']}", value=f"相似度: {result['similarity']:.4f}", delta=f"类型: {result['type']}")
        
        st.subheader("📊 光谱对比图")
        # 注意：画图时也用处理后的 final_sample_data，保证图表和结果一致
        chart_data = pd.DataFrame({'波数 (cm⁻¹)': target_wavenumbers, '样品(处理后)': final_sample_data})
        for i, result in enumerate(top5[:3], 1):
            spec = next(s for s in db_spectra if s['name'] == result['name'])
            db_interpolated = interpolate_spectrum(spec['wavenumbers'], spec['intensities'], target_wavenumbers)
            chart_data[f'Top{i}: {result["name"]}'] = db_interpolated
        st.line_chart(chart_data.set_index('波数 (cm⁻¹)'))
    else:
        st.error("❌ 样品与数据库光谱无重叠波数范围")