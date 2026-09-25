import sqlite3
import pandas as pd
import json
import os

# 配置
FOLDER_NAME = "xrf_standard"
DB_NAME = "spectrum_data.db"

def import_xrf_standard():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. 检查文件夹是否存在
    if not os.path.exists(FOLDER_NAME):
        print(f"❌ 错误：找不到 '{FOLDER_NAME}' 文件夹！请确认已在根目录下创建该文件夹。")
        return
        
    files = [f for f in os.listdir(FOLDER_NAME) if f.endswith('.csv')]
    if not files:
        print(f"⚠️ 警告：'{FOLDER_NAME}' 文件夹里没有 CSV 文件。")
        return
    
    print(f"🔍 发现 {len(files)} 个文件，开始导入标准库...")
    success_count = 0
    
    try:
        for file_name in files:
            file_path = os.path.join(FOLDER_NAME, file_name)
            try:
                # 2. 读取 CSV
                df = pd.read_csv(file_path, header=None)
                
                # 提取第一列（能量/波数）和第二列（强度）
                x_axis = df.iloc[:, 0].values.astype(float)
                y_axis = df.iloc[:, 1].values.astype(float)
                
                # 3. 构建 JSON 数据
                data_dict = {
                    'wavenumbers': x_axis.tolist(), # 数据库字段习惯叫 wavenumbers，这里存 XRF 的 energy
                    'intensities': y_axis.tolist()
                }
                data_json = json.dumps(data_dict)
                
                # 获取文件名（不含 .csv）作为物质名称
                material_name = os.path.splitext(file_name)[0]
                
                # 4. 插入数据库，注意 source_tag = 'Standard' 和 spectrum_type = 'XRF'
                cursor.execute(
                    "INSERT INTO spectra (file_name, material_name, spectrum_type, data_json, source_tag) VALUES (?, ?, ?, ?, ?)",
                    (file_name, material_name, "XRF", data_json, "Standard")
                )
                success_count += 1
                
            except Exception as e:
                print(f"❌ 导入文件 {file_name} 失败: {e}")
                
        conn.commit()
        print(f"\n🎉 导入完成！成功添加 {success_count}/{len(files)} 个 XRF 标准谱图到数据库。")
        
    finally:
        conn.close()

if __name__ == "__main__":
    import_xrf_standard()