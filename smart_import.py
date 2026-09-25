import csv
import sqlite3
import os
import json

# 📁 设置你的文件夹路径
FTIR_FOLDER = 'infraart_FTIR_CSV_Files'
XRF_FOLDER = 'infraart_XRFcsv'
RAMAN_FOLDER = 'inraart_Raman_CSV' # 👈 新增拉曼专属文件夹
DB_FILE = 'spectrum_data.db'

def init_db():
    """初始化或连接数据库"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS spectra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spectrum_name TEXT,
            spectrum_type TEXT,
            source_tag TEXT,
            wavenumbers TEXT,
            intensities TEXT
        )
    ''')
    conn.commit()
    return conn

def import_folder(folder_path, target_type, conn):
    """智能读取并导入指定文件夹下的所有 CSV 文件"""
    cursor = conn.cursor()
    imported_count = 0

    if not os.path.exists(folder_path):
        print(f"⚠️ 警告：文件夹 {folder_path} 不存在，跳过。")
        return

    print(f"\n🚀 正在扫描并处理文件夹: {folder_path} (目标类型: {target_type})")

    # 遍历文件夹中的所有 CSV 文件
    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    headers = next(reader)  # 获取第一行表头
                    
                    # 智能识别波长/能量列和强度列
                    col_wavenumber = None
                    col_intensity = None
                    
                    for i, header in enumerate(headers):
                        lower_header = header.lower()
                        # 识别波数/能量
                        if any(word in lower_header for word in ['wavenumber', 'wavenum', 'cm-1']):
                            col_wavenumber = i
                        # 识别强度
                        elif any(word in lower_header for word in ['transmittance', 'absorbance', 'intensity', 'count rate']):
                            col_intensity = i
                    
                    if col_wavenumber is not None and col_intensity is not None:
                        wavenumbers = []
                        intensities = []
                        
                        for row in reader:
                            if len(row) > max(col_wavenumber, col_intensity):
                                try:
                                    wavenumbers.append(float(row[col_wavenumber]))
                                    intensities.append(float(row[col_intensity]))
                                except ValueError:
                                    continue 

                        if len(wavenumbers) > 0:
                            # 存入数据库
                            cursor.execute(
                                'INSERT INTO spectra (spectrum_name, spectrum_type, source_tag, wavenumbers, intensities) VALUES (?, ?, ?, ?, ?)',
                                (filename, target_type, 'Standard', json.dumps(wavenumbers), json.dumps(intensities))
                            )
                            imported_count += 1
                            print(f"  ✅ 成功导入: {filename}")
                        else:
                            print(f"  ❌ 失败 (无有效数据): {filename}")
                    else:
                        print(f"  ❌ 失败 (无法识别列名): {filename}")
            except Exception as e:
                print(f"  ❌ 处理文件时出错 {filename}: {e}")

    conn.commit()
    print(f"📥 {folder_path} 导入完成，共成功导入 {imported_count} 条数据。")

if __name__ == "__main__":
    print("🚀 启动光谱数据智能导入系统...")
    
    connection = init_db()
    
    # 👇 按顺序导入三种类型的数据
    import_folder(FTIR_FOLDER, 'FTIR', connection)
    import_folder(XRF_FOLDER, 'XRF', connection)
    import_folder(RAMAN_FOLDER, 'Raman', connection) # 👈 新增导入拉曼
    
    # 验证导入结果
    cursor = connection.cursor()
    cursor.execute("SELECT spectrum_type, COUNT(*) FROM spectra GROUP BY spectrum_type")
    results = cursor.fetchall()
    connection.close()
    
    print("\n📊 数据库当前状态：")
    for r in results:
        print(f"  - {r[0]}: {r[1]} 条")
    print("\n🎉 导入全部完成！请重启你的 Streamlit 服务以加载新数据。")