import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from scipy.stats import pearsonr
import sqlite3
import os
import glob

# ==========================================
# 配置区域 (在这修改文件路径)
# ==========================================
INPUT_FOLDER = "./aging_samples"  # 存放所有老化谱图的文件夹
STANDARD_DB_PATH = "./standard_library.csv" # 外接的标准数据库文件 (CSV格式)
OUTPUT_DB_PATH = "./analysis_results.db"    # 输出的结果数据库

# ==========================================
# 1. 加载外接标准数据库 (包含材料名、特征峰位置、特征强度等)
# ==========================================
def load_standard_library(file_path):
    print(f">>> [系统] 正在加载外接标准数据库：{file_path} ...")
    if not os.path.exists(file_path):
        # 如果没有文件，创建一个模拟的用于演示
        print("   (未找到文件，生成模拟标准库...)")
        data = {
            'Material_Name': ['Material_A', 'Material_B', 'Material_C'],
            'Peak_Pos_1': [450, 600, 500],   # 第一个特征峰位置
            'Peak_Int_1': [1.0, 0.8, 0.9],   # 第一个特征峰相对强度
            'Peak_Pos_2': [550, 700, 650],   # 第二个特征峰位置
            'Peak_Int_2': [0.5, 0.9, 0.4]    # 第二个特征峰相对强度
        }
        df = pd.DataFrame(data)
        df.to_csv(file_path, index=False)
        return df
    
    return pd.read_csv(file_path)

# ==========================================
# 2. 核心算法：识别特征峰
# ==========================================
def extract_features(wavelengths, intensities):
    """
    使用 scipy.find_peaks 自动寻找特征峰
    返回：峰的波长位置列表，峰的强度列表
    """
    # 参数说明:
    # height=0.1: 只找强度大于0.1的峰 (去除噪音)
    # distance=20: 两个峰之间至少间隔20个数据点 (避免把一个小抖动当成峰)
    # prominence=0.05: 峰的突出程度，过滤掉平缓的隆起
    peaks, properties = find_peaks(intensities, height=0.1, distance=20, prominence=0.05)
    
    peak_positions = wavelengths[peaks]
    peak_intensities = intensities[peaks]
    
    return peak_positions, peak_intensities

# ==========================================
# 3. 核心算法：基于特征峰的匹配逻辑
# ==========================================
def match_by_features(sample_peaks_pos, sample_peaks_int, standard_lib):
    best_match = None
    max_score = -1
    
    print(f"   -> 检测到 {len(sample_peaks_pos)} 个特征峰: {np.round(sample_peaks_pos, 1)}")
    
    for index, row in standard_lib.iterrows():
        mat_name = row['Material_Name']
        score = 0
        matched_count = 0
        
        # 简单逻辑：看样品的峰能不能在标准库里找到对应位置的峰
        # 允许 +/- 10nm 的误差 (仪器误差或老化位移)
        tolerance = 10 
        
        std_peaks_pos = [row['Peak_Pos_1'], row['Peak_Pos_2']] # 假设标准库存了两个主峰
        std_peaks_int = [row['Peak_Int_1'], row['Peak_Int_2']]
        
        for s_pos, s_int in zip(sample_peaks_pos, sample_peaks_int):
            # 检查这个峰是否匹配标准库里的任意一个峰
            for i, std_pos in enumerate(std_peaks_pos):
                if abs(s_pos - std_pos) <= tolerance:
                    matched_count += 1
                    # 分数计算：位置越近分越高，强度越接近分越高
                    pos_score = 1 - (abs(s_pos - std_pos) / tolerance)
                    int_score = 1 - abs(s_int - std_peaks_int[i])
                    score += (pos_score * 0.7 + int_score * 0.3) # 位置权重70%，强度30%
                    break
        
        # 归一化分数
        if len(sample_peaks_pos) > 0:
            final_score = score / (len(sample_peaks_pos) * 1.0) # 简单归一化
        else:
            final_score = 0
            
        if final_score > max_score:
            max_score = final_score
            best_match = mat_name
            
    return best_match, max_score

# ==========================================
# 4. 批量处理主程序
# ==========================================
def run_batch_analysis():
    # 1. 加载标准库
    std_lib = load_standard_library(STANDARD_DB_PATH)
    
    # 2. 准备结果数据库
    conn = sqlite3.connect(OUTPUT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS batch_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            instrument_id TEXT,
            detected_peaks TEXT,
            matched_material TEXT,
            confidence_score REAL,
            analysis_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. 获取所有文件 (支持 .csv, .xlsx, .txt)
    files = glob.glob(os.path.join(INPUT_FOLDER, "*.csv")) 
    # 如果没有文件夹，创建一些模拟数据用于演示
    if not files:
        print(f">>> [提示] 未在 {INPUT_FOLDER} 找到文件，正在生成模拟数据演示...")
        os.makedirs(INPUT_FOLDER, exist_ok=True)
        for i in range(3):
            w = np.linspace(200, 800, 601)
            # 模拟 Material_A 的老化数据 (峰在450附近)
            y = np.exp(-((w - (450 + np.random.randint(-5, 5)))**2) / (2 * 50**2)) + np.random.normal(0, 0.05, 601)
            df = pd.DataFrame({'Wavelength': w, 'Intensity': y, 'Instrument': 'Spec_001'})
            df.to_csv(os.path.join(INPUT_FOLDER, f"sample_{i}.csv"), index=False)
        files = glob.glob(os.path.join(INPUT_FOLDER, "*.csv"))

    print(f"\n>>> [系统] 发现 {len(files)} 个文件，开始批量分析...\n")

    for file_path in files:
        filename = os.path.basename(file_path)
        print(f"--- 正在处理：{filename} ---")
        
        try:
            # 读取数据
            df = pd.read_csv(file_path)
            # 自动识别列名 (假设前两列是波长和强度)
            cols = df.columns
            w_col, i_col = cols[0], cols[1]
            inst_col = cols[2] if len(cols) > 2 else "Unknown"
            
            wavelengths = df[w_col].values
            intensities = df[i_col].values
            instrument = df[inst_col].iloc[0] if len(cols) > 2 else "Unknown"
            
            # A. 提取特征峰
            p_pos, p_int = extract_features(wavelengths, intensities)
            
            if len(p_pos) == 0:
                print("   -> 未检测到有效特征峰，跳过。")
                continue
                
            # B. 与标准库比对
            matched_mat, score = match_by_features(p_pos, p_int, std_lib)
            
            result_str = f"匹配结果：{matched_mat} (置信度：{score:.2f})"
            print(f"   -> {result_str}")
            
            # C. 存入数据库
            peaks_str = ",".join([f"{p:.1f}" for p in p_pos])
            cursor.execute('''
                INSERT INTO batch_results (file_name, instrument_id, detected_peaks, matched_material, confidence_score)
                VALUES (?, ?, ?, ?, ?)
            ''', (filename, instrument, peaks_str, matched_mat, score))
            
        except Exception as e:
            print(f"   -> 错误：{e}")
            
    conn.commit()
    conn.close()
    print(f"\n=== 全部完成！结果已保存至 {OUTPUT_DB_PATH} ===")

if __name__ == "__main__":
    run_batch_analysis()