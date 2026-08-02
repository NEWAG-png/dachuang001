import streamlit as st
import pandas as pd
import sqlite3
import json
import numpy as np
import os
import ast  # 关键库：用于解析非标准JSON（如单引号列表）
from scipy.interpolate import interp1d

# 设置页面配置
st.set_page_config(page_title="FTIR 红外光谱智能检索系统", layout="wide")
st.title("🔬 FTIR 红外光谱智能检索系统 (Top 5 匹配版)")

# --- 1. 侧边栏上传文件 ---
with st.sidebar:
    st.header("📂 上传样品数据")
    uploaded_file = st.file_uploader("请上传 CSV 或 JSON 文件", type=["csv", "json"])
    
    if uploaded_file is not None:
        st.success(f"已加载: {uploaded_file.name}")

# --- 2. 核心工具函数 ---

def parse_json_safe(json_str):
    """
    万能解析器：尝试用 json.loads 解析，失败则用 ast.literal_eval 解析
    解决数据库中存储格式不统一的问题
    """
    if not json_str or not isinstance(json_str, str):
        return None
    
    try:
        # 尝试标准 JSON 解析
        data = json.loads(json_str)
    except json.JSONDecodeError:
        try:
            # 尝试 Python 字面量解析（处理单引号列表等情况）
            data = ast.literal_eval(json_str)
        except (ValueError, SyntaxError):
            return None
    
    # 确保解析出来的是字典，且包含必要字段
    if isinstance(data, dict) and 'wavenumbers' in data and 'intensities' in data:
        return data
    return None

def load_database_spectra():
    """
    从数据库加载所有光谱数据，自动跳过坏数据
    """
    db_path = 'spectrum_data.db'
    if not os.path.exists(db_path):
        st.error(f"❌ 找不到数据库文件: {db_path}")
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询所有光谱数据
        cursor.execute("SELECT id, material_name, spectrum_type, data_json FROM spectra")
        rows = cursor.fetchall()
        conn.close()
        
        valid_spectra = []
        invalid_count = 0
        
        for row in rows:
            spec_id, material_name, spectrum_type, data_json_str = row
            
            # 使用万能解析器解析数据
            parsed_data = parse_json_safe(data_json_str)
            
            if parsed_data:
                try:
                    # 将波数和强度转换为 numpy 数组
                    wavenumbers = np.array(parsed_data['wavenumbers'], dtype=float)
                    intensities = np.array(parsed_data['intensities'], dtype=float)
                    
                    valid_spectra.append({
                        'id': spec_id,
                        'name': material_name,
                        'type': spectrum_type,
                        'wavenumbers': wavenumbers,
                        'intensities': intensities
                    })
                except (ValueError, TypeError) as e:
                    invalid_count += 1
            else:
                invalid_count += 1
        
        if invalid_count > 0:
            st.warning(f"⚠️ 数据库中有 {invalid_count} 条数据格式异常，已自动跳过")
        
        return valid_spectra
        
    except Exception as e:
        st.error(f"❌ 读取数据库失败: {str(e)}")
        return []

def parse_uploaded_file(uploaded_file):
    """
    解析上传的 CSV 或 JSON 文件
    """
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            # 假设 CSV 有两列：波数和强度
            if len(df.columns) >= 2:
                wavenumbers = df.iloc[:, 0].values.astype(float)
                intensities = df.iloc[:, 1].values.astype(float)
                return wavenumbers, intensities
            else:
                raise ValueError("CSV 文件至少需要两列数据")
                
        elif uploaded_file.name.endswith('.json'):
            content = uploaded_file.read().decode('utf-8')
            data = json.loads(content)
            if 'wavenumbers' in data and 'intensities' in data:
                wavenumbers = np.array(data['wavenumbers'], dtype=float)
                intensities = np.array(data['intensities'], dtype=float)
                return wavenumbers, intensities
            else:
                raise ValueError("JSON 文件必须包含 'wavenumbers' 和 'intensities' 字段")
                
    except Exception as e:
        st.error(f"❌ 文件解析失败: {str(e)}")
        return None, None

def interpolate_spectrum(wavenumbers, intensities, target_wavenumbers):
    """
    将光谱插值到目标波数范围
    """
    # 确保波数是递增的
    sort_idx = np.argsort(wavenumbers)
    wavenumbers = wavenumbers[sort_idx]
    intensities = intensities[sort_idx]
    
    # 创建插值函数
    interp_func = interp1d(wavenumbers, intensities, kind='linear', 
                          bounds_error=False, fill_value=0.0)
    
    # 插值到目标波数
    interpolated_intensities = interp_func(target_wavenumbers)
    return interpolated_intensities

def calculate_similarity(spec1_intensities, spec2_intensities):
    """
    计算两个光谱的相似度（余弦相似度）
    """
    # 归一化
    norm1 = np.linalg.norm(spec1_intensities)
    norm2 = np.linalg.norm(spec2_intensities)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    normalized_spec1 = spec1_intensities / norm1
    normalized_spec2 = spec2_intensities / norm2
    
    # 计算余弦相似度
    cosine_sim = np.dot(normalized_spec1, normalized_spec2)
    return cosine_sim

# --- 3. 主程序逻辑 ---

# 加载数据库光谱
db_spectra = load_database_spectra()

if not db_spectra:
    st.warning("⚠️ 数据库为空或无法读取有效数据。")
else:
    st.success(f"✅ 成功加载 {len(db_spectra)} 条数据库光谱")

# 处理上传文件
if uploaded_file is not None:
    sample_wavenumbers, sample_intensities = parse_uploaded_file(uploaded_file)
    
    if sample_wavenumbers is not None:
        st.success(f"✅ 样品解析成功！点数: {len(sample_wavenumbers)}")
        
        # 找到所有光谱的共同波数范围
        all_wavenumbers = [sample_wavenumbers] + [spec['wavenumbers'] for spec in db_spectra]
        min_wn = max(np.min(wn) for wn in all_wavenumbers)
        max_wn = min(np.max(wn) for wn in all_wavenumbers)
        
        if min_wn >= max_wn:
            st.error("❌ 样品与数据库光谱无重叠波数范围")
        else:
            # 创建目标波数数组
            target_wavenumbers = np.arange(min_wn, max_wn, 1.0)
            
            # 插值样品光谱
            sample_interpolated = interpolate_spectrum(
                sample_wavenumbers, sample_intensities, target_wavenumbers
            )
            
            # 计算与所有数据库光谱的相似度
            similarities = []
            for spec in db_spectra:
                db_interpolated = interpolate_spectrum(
                    spec['wavenumbers'], spec['intensities'], target_wavenumbers
                )
                sim = calculate_similarity(sample_interpolated, db_interpolated)
                similarities.append({
                    'name': spec['name'],
                    'type': spec['type'],
                    'similarity': sim
                })
            
            # 按相似度排序，取 Top 5
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            top5 = similarities[:5]
            
            # 显示结果
            st.subheader("🏆 Top 5 匹配结果")
            for i, result in enumerate(top5, 1):
                st.metric(
                    label=f"第 {i} 名: {result['name']}",
                    value=f"相似度: {result['similarity']:.4f}",
                    delta=f"类型: {result['type']}"
                )
            
            # 绘制对比图
            st.subheader("📊 光谱对比图")
            chart_data = pd.DataFrame({
                '波数 (cm⁻¹)': target_wavenumbers,
                '样品': sample_interpolated
            })
            
            for i, result in enumerate(top5[:3], 1):  # 只画前3名避免太乱
                spec = next(s for s in db_spectra if s['name'] == result['name'])
                db_interpolated = interpolate_spectrum(
                    spec['wavenumbers'], spec['intensities'], target_wavenumbers
                )
                chart_data[f'Top{i}: {result["name"]}'] = db_interpolated
            
            st.line_chart(chart_data.set_index('波数 (cm⁻¹)'))