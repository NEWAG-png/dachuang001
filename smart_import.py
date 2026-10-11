import csv
import sqlite3
import os
import json
import pandas as pd  #处理无表头数据
#1.设置路径
FTIR_FOLDER = 'infraart_FTIR_csv'
XRF_FOLDER = 'infraart_XRF_csv'
RAMAN_FOLDER = 'infraart_Raman_CSV'
XRD_FOLDER = 'XRD_csv'
FTIR_REF_FOLDER = 'FTIR_with_references'
DB_FILE = 'spectrum_db.sqlite'
def init_db():
    """初始化连接数据库，确保表结构正确"""
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
    # 【新增】给 spectrum_name + spectrum_type 加唯一约束，防止重复导入
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_spectrum_unique 
        ON spectra(spectrum_name, spectrum_type)
    ''')
    conn.commit()
    return conn

def _check_duplicate(cursor, spectrum_name, spectrum_type):
    """检查是否已存在相同的谱图名称+类型，返回True表示已存在(需跳过)"""
    cursor.execute(
        'SELECT COUNT(*) FROM spectra WHERE spectrum_name = ? AND spectrum_type = ?',
        (spectrum_name, spectrum_type)
    )
    count = cursor.fetchone()[0]
    return count > 0

def import_folder(folder_path, target_type, conn):
    """智能读取并导入指定文件夹下的所有CSV文件（FTIR/XRF/Raman）"""
    cursor = conn.cursor()
    imported_count = 0
    skipped_count = 0
    if not os.path.exists(folder_path):
        print(f"警告：文件夹 {folder_path} 不存在，跳过。")
        return
    print(f"\n正在扫描并处理文件夹: {folder_path} (目标类型: {target_type})")
    #遍历所有CSV文件
    for filename in os.listdir(folder_path):
        if filename.endswith('.csv'):
            file_path = os.path.join(folder_path, filename)
            try:
                # 【新增】重复检测：如果已存在则跳过
                if _check_duplicate(cursor, filename, target_type):
                    print(f"  ⏭️ 已存在(跳过): {filename}")
                    skipped_count += 1
                    continue
                with open(file_path, 'r', encoding='utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    headers = next(reader)  # 获取第一行表头
                    # 智能识别列索引
                    col_wavenumber = None
                    col_intensity = None
                    for i, header in enumerate(headers):
                        lower_header = header.lower()
                        if any(word in lower_header for word in ['wavenumber', 'energy', 'wavenum', 'cm-1']):
                            col_wavenumber = i
                        elif any(word in lower_header for word in ['transmittance', 'absorbance', 'intensity', 'count rate']):
                            col_intensity = i
                    if col_wavenumber is not None and col_intensity is not None:
                        wavenumbers = []
                        intensities = [] 
                        #提取数据
                        for row in reader:
                            if len(row) > max(col_wavenumber, col_intensity):
                                try:
                                    wavenumbers.append(float(row[col_wavenumber]))
                                    intensities.append(float(row[col_intensity]))
                                except ValueError:
                                    continue #跳过非数字的行
                        if len(wavenumbers) > 0:
                            #存入
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
    print(f"📥 {folder_path} 导入完成，共成功导入 {imported_count} 条数据，跳过 {skipped_count} 条重复。")
def import_xrd_folder(folder_path, target_type, conn):
    """递归扫描文件夹，处理无表头的XRD数据"""
    cursor = conn.cursor()
    imported_count = 0
    skipped_count = 0
    if not os.path.exists(folder_path):
        print(f"警告：文件夹 {folder_path} 不存在，跳过。")
        return
    print(f"\n正在扫描 XRD 论文文件夹: {folder_path}")
    # 遍历根目录下的所有文件夹，即论文标题
    for subfolder_name in os.listdir(folder_path):
        subfolder_path = os.path.join(folder_path, subfolder_name)
        if os.path.isdir(subfolder_path) and not subfolder_name.startswith('.'):
            print(f"  📂 正在扫描论文: {subfolder_name}")
            #遍历论文文件夹里的文件
            for filename in os.listdir(subfolder_path):
                if filename.endswith('.csv'):
                    file_path = os.path.join(subfolder_path, filename)
                    try:
                        # 【新增】重复检测
                        if _check_duplicate(cursor, filename, target_type):
                            print(f"    ⏭️ 已存在(跳过): {filename}")
                            skipped_count += 1
                            continue
                        #无表头读取，直接按列索引抓取数据
                        df = pd.read_csv(file_path, header=None)
                        angles = []
                        intensities = []
                        # 检查数据是否有两列，防止读入空文件或坏文件
                        if df.shape[1] >= 2:
                            # 第一列当作角度，第二列当作强度
                            angles = df[0].dropna().astype(float).tolist()
                            intensities = df[1].dropna().astype(float).tolist()
                        if len(angles) > 0:
                            #论文标题存入source_tag
                            cursor.execute(
                                'INSERT INTO spectra (spectrum_name, spectrum_type, source_tag, wavenumbers, intensities) VALUES (?, ?, ?, ?, ?)',
                                (filename, target_type, subfolder_name, json.dumps(angles), json.dumps(intensities))
                            )
                            imported_count += 1
                    except Exception as e:
                        print(f"    ❌ 处理文件 {filename} 时出错: {e}")
    conn.commit()
    print(f"📥 XRD 导入完成，共成功导入 {imported_count} 条数据，跳过 {skipped_count} 条重复。")
def import_ftir_ref_folder(folder_path, target_type, conn):
    """【新增】递归扫描文件夹，处理无表头的FTIR数据（带文献来源）
    
    文件夹结构要求：
    FTIR_with_references/
    ├── 期刊名1/
    │   ├── sample01.csv
    │   └── sample02.csv
    ├── 期刊名2/
    │   └── sample03.csv
    
    CSV文件格式：无表头，纯数字，两列（波数, 强度）
    """
    cursor = conn.cursor()
    imported_count = 0
    skipped_count = 0
    if not os.path.exists(folder_path):
        print(f"警告：文件夹 {folder_path} 不存在，跳过。")
        print(f"  请确保已将学姐的FTIR数据解压到该文件夹下。")
        return
    print(f"\n正在扫描 FTIR 带文献文件夹: {folder_path}")
    # 遍历根目录下的所有文件夹，即期刊名/文献名
    for journal_name in os.listdir(folder_path):
        journal_folder = os.path.join(folder_path, journal_name)
        if os.path.isdir(journal_folder) and not journal_name.startswith("."):
            print(f"  📂 正在扫描期刊: {journal_name}")
            # 遍历期刊文件夹里的CSV文件
            for filename in os.listdir(journal_folder):
                if filename.endswith(".csv"):
                    file_path = os.path.join(journal_folder, filename)
                    try:
                        # 【新增】重复检测：防止重复导入
                        if _check_duplicate(cursor, filename, target_type):
                            print(f"    ⏭️ 已存在(跳过): {filename}")
                            skipped_count += 1
                            continue
                        
                        # 无表头读取，直接按列索引抓取数据
                        df = pd.read_csv(file_path, header=None)
                        wavenumbers = []
                        intensities = []
                        # 检查数据是否有两列，防止读入空文件或坏文件
                        if df.shape[1] >= 2:
                            # 第一列当作波数(wavenumber)，第二列当作强度(intensity)
                            wavenumbers = df[0].dropna().astype(float).tolist()
                            intensities = df[1].dropna().astype(float).tolist()
                        if len(wavenumbers) > 0:
                            # 期刊名存入source_tag（这样前端就能显示文献来源了）
                            cursor.execute(
                                'INSERT INTO spectra (spectrum_name, spectrum_type, source_tag, wavenumbers, intensities) VALUES (?, ?, ?, ?, ?)',
                                (filename, target_type, journal_name, json.dumps(wavenumbers), json.dumps(intensities))
                            )
                            imported_count += 1
                            print(f"    ✅ 成功导入: {filename} (文献: {journal_name})")
                        else:
                            print(f"    ❌ 失败 (无有效数据): {filename}")
                    except Exception as e:
                        print(f"    ❌ 处理文件 {filename} 时出错: {e}")
    conn.commit()
    print(f"📥 FTIR 带文献导入完成，共成功导入 {imported_count} 条数据，跳过 {skipped_count} 条重复。")

if __name__ == "__main__":
    print("🚀 启动光谱数据智能导入系统...")
    #连接数据库
    connection = init_db()
    #执行导入
    import_folder(FTIR_FOLDER, 'FTIR', connection)
    import_folder(XRF_FOLDER, 'XRF', connection)
    import_folder(RAMAN_FOLDER, 'Raman', connection)
    #处理 XRD 多级目录
    import_xrd_folder(XRD_FOLDER, 'XRD', connection)
    # 【新增】处理带文献来源的FTIR数据
    import_ftir_ref_folder(FTIR_REF_FOLDER, 'FTIR', connection)
    #验证导入结果
    cursor = connection.cursor()
    cursor.execute("SELECT spectrum_type, COUNT(*) FROM spectra GROUP BY spectrum_type")
    results = cursor.fetchall()
    connection.close()  
    print("\n📊 数据库当前状态：")
    for r in results:
        print(f"  - {r[0]}: {r[1]} 条")
    print("\n🎉 导入全部完成！请重启你的 Streamlit 服务以加载新数据。")