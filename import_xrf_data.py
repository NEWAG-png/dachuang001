import os
import pandas as pd
import json
import sqlite3
from datetime import datetime

# ========== 配置区 ==========
DB_PATH = "spectrum_data.db"
CSV_FOLDER = "infraart XRFcsv"
SPECTRUM_TYPE = "XRF"
# ============================

def process_xrf_csv(file_path):
    """解析 XRF CSV 文件，返回 JSON 格式的光谱数据"""
    try:
        df = pd.read_csv(file_path, header=0)
        
        x_col = None
        y_col = None
        for col in df.columns:
            col_lower = str(col).lower()
            if 'energy' in col_lower or 'kev' in col_lower:
                x_col = col
            if 'net' in col_lower or 'count' in col_lower or 'intensity' in col_lower:
                y_col = col
        
        if not x_col or not y_col:
            return None, "无法识别列名"
        
        x_data = df[x_col].dropna().tolist()
        y_data = df[y_col].dropna().tolist()
        
        min_len = min(len(x_data), len(y_data))
        x_data = x_data[:min_len]
        y_data = y_data[:min_len]
        
        data_json = json.dumps({"x": x_data, "y": y_data})
        return data_json, None
        
    except Exception as e:
        return None, str(e)

def main():
    if not os.path.exists(CSV_FOLDER):
        print(f"❌ 找不到文件夹: {CSV_FOLDER}")
        return
    
    csv_files = [f for f in os.listdir(CSV_FOLDER) if f.lower().endswith('.csv')]
    if not csv_files:
        print(f"❌ {CSV_FOLDER} 里没有 CSV 文件")
        return
    
    print(f"📂 找到 {len(csv_files)} 个 CSV 文件，开始导入...\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for filename in csv_files:
        file_path = os.path.join(CSV_FOLDER, filename)
        material_name = os.path.splitext(filename)[0]
        
        # 检查是否已存在
        cursor.execute("SELECT id FROM spectra WHERE file_name = ?", (filename,))
        if cursor.fetchone():
            skip_count += 1
            print(f"⏭️  跳过（已存在）: {filename}")
            continue
        
        data_json, error = process_xrf_csv(file_path)
        if error:
            fail_count += 1
            print(f"❌ 失败: {filename} - {error}")
            continue
        
        cursor.execute(
            "INSERT INTO spectra (file_name, material_name, spectrum_type, data_json, source_tag, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (filename, material_name, SPECTRUM_TYPE, data_json, "XRF标准库", datetime.now().isoformat())
        )
        success_count += 1
        print(f"✅ 成功: {filename}")
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*40}")
    print(f"📊 导入完成！")
    print(f"   成功: {success_count} 条")
    print(f"   跳过: {skip_count} 条")
    print(f"   失败: {fail_count} 条")
    print(f"{'='*40}")

if __name__ == "__main__":
    main()