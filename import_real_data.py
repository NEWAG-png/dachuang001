import os
import json
import sqlite3
import pandas as pd
import traceback

# ================= 配置区 =================
# 【重要】请确保这两个文件夹名字和你电脑上一模一样（包括空格）
FOLDER_STANDARD = "infraart标准谱图" 
FOLDER_UNKNOWN = "infraart_FTIR_CSV_Files"
DB_NAME = "spectrum_data.db"

# ================= 1. 数据库初始化 =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # 建表语句 (如果表已存在则忽略)
    c.execute('''CREATE TABLE IF NOT EXISTS spectra (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_name TEXT,
                    spectrum_type TEXT,
                    file_name TEXT,
                    data_json TEXT
                )''')
    conn.commit()
    return conn

# ================= 2. 核心导入逻辑 =================
def import_data_from_folder(conn, folder_path, source_tag):
    """
    从指定文件夹读取 CSV 并写入数据库
    :param conn: 数据库连接
    :param folder_path: 文件夹的绝对路径
    :param source_tag: 'Standard' 或 'Unknown'
    """
    if not os.path.exists(folder_path):
        print(f"❌ 错误：找不到文件夹 -> {folder_path}")
        print(f"   请检查文件夹名称是否包含空格，或是否在当前目录下。")
        return 0

    files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    if not files:
        print(f"⚠️ 文件夹是空的，或者没有 .csv 文件：{folder_path}")
        return 0

    print(f"🚀 开始扫描：{os.path.basename(folder_path)} (共 {len(files)} 个文件)...")
    
    success_count = 0
    fail_count = 0

    for filename in files:
        file_path = os.path.join(folder_path, filename)
        try:
            # 读取 CSV (尝试多种编码)
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='gbk')

            # --- 数据清洗与格式化 ---
            # 假设 CSV 只有两列：波数(X) 和 强度(Y)
            # 如果有多余的表头行，pandas 通常能处理，但如果第一行就是数据，需要确认列名
            
            # 获取第一列和第二列的数据
            x_data = df.iloc[:, 0].tolist() # 波数
            y_data = df.iloc[:, 1].tolist() # 强度
            
            # 构建 JSON 对象
            spectrum_data = {
                "wavenumbers": [float(x) for x in x_data],
                "intensities": [float(y) for y in y_data]
            }
            
            # 提取物质名称 (去掉 .csv 后缀)
            material_name = os.path.splitext(filename)[0]

            # 写入数据库
            conn.execute(
                "INSERT INTO spectra (material_name, spectrum_type, file_name, data_json) VALUES (?, ?, ?, ?)",
                (material_name, source_tag, filename, json.dumps(spectrum_data))
            )
            success_count += 1

        except Exception as e:
            print(f"⚠️ 处理失败 {filename}: {e}")
            fail_count += 1

    conn.commit()
    print(f"✅ 完成！成功导入 {success_count} 条，失败 {fail_count} 条。\n")
    return success_count

# ================= 3. 主程序入口 =================
if __name__ == "__main__":
    # 获取当前脚本所在的绝对路径，防止路径找不到
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    print(f"📂 当前工作目录: {BASE_DIR}")
    
    # 拼接出完整的文件夹路径
    path_std = os.path.join(BASE_DIR, FOLDER_STANDARD)
    path_unk = os.path.join(BASE_DIR, FOLDER_UNKNOWN)

    # 检查文件夹是否存在 (调试用)
    if not os.path.exists(path_std):
        print(f"❌ 找不到标准谱图文件夹: {path_std}")
        print("   请把 'infraart标准谱图' 文件夹放到和脚本同一个目录下！")
    if not os.path.exists(path_unk):
        print(f"❌ 找不到待测谱图文件夹: {path_unk}")

    # 连接数据库
    conn = init_db()
    
    # 开始导入
    # 注意：如果你的文件夹名字不一样，请修改上面的 FOLDER_STANDARD 变量
    import_data_from_folder(conn, path_std, "Standard")
    import_data_from_folder(conn, path_unk, "Unknown")
    
    conn.close()
    input("按回车键退出...") # 防止窗口一闪而过