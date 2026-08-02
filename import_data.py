import pandas as pd
import sqlite3
import os

# 配置：数据库在当前目录，数据在 data 子文件夹
DB_NAME = 'spectrum_data.db'
DATA_FOLDER = 'data' 

def import_csv_to_db():
    if not os.path.exists(DB_NAME):
        print("❌ 没找到数据库文件，请先运行 init_db.py")
        return

    # 检查 data 文件夹是否存在
    full_data_path = os.path.join(os.getcwd(), DATA_FOLDER)
    if not os.path.exists(full_data_path):
        print(f"❌ 没找到 {DATA_FOLDER} 文件夹，请确认路径正确")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 获取 data 目录下所有 csv 文件
    files = [f for f in os.listdir(DATA_FOLDER) if f.lower().endswith('.csv')]
    
    if not files:
        print(f"⚠️ 在 {DATA_FOLDER} 目录下没找到 CSV 文件")
        conn.close()
        return

    print(f"🔍 发现 {len(files)} 个数据文件，开始导入...\n")
    
    success_count = 0
    for file in files:
        try:
            file_path = os.path.join(DATA_FOLDER, file)
            
            # 尝试读取 CSV
            # 假设第一列是波数，第二列是吸光度
            # 如果 CSV 有表头，pandas 会自动处理；如果没有，header=None 更安全
            # 这里我们尝试自动推断，如果报错再调整
            try:
                df = pd.read_csv(file_path, header=None, names=['wavenumber', 'absorbance'])
            except:
                df = pd.read_csv(file_path)
                # 如果读进来列名不是我们要的，强制重命名前两列
                if 'wavenumber' not in df.columns:
                    df.columns = ['wavenumber', 'absorbance'] + list(df.columns[2:])

            # 简单的清洗：去掉空值，只保留前两列
            df = df[['wavenumber', 'absorbance']].dropna()
            
            # 获取样本名（去掉 .csv 后缀）
            sample_name = os.path.splitext(file)[0]
            df['sample_name'] = sample_name
            
            # 批量插入数据
            data_to_insert = df[['sample_name', 'wavenumber', 'absorbance']].values.tolist()
            
            cursor.executemany(
                "INSERT INTO spectra (sample_name, wavenumber, absorbance) VALUES (?, ?, ?)", 
                data_to_insert
            )
            success_count += 1
            print(f"  ✅ 已导入: {file} ({len(df)} 个数据点)")
            
        except Exception as e:
            print(f"  ❌ 导入失败 {file}: {e}")

    conn.commit()
    conn.close()
    print(f"\n🎉 全部完成！成功导入 {success_count} 个文件。")

if __name__ == "__main__":
    import_csv_to_db()